"""Root Cause Analysis and troubleshooting tools for pfSense MCP server.

All tools in this module are READ-ONLY — they diagnose issues without making
any configuration changes to the pfSense appliance.
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..guardrails import get_rollback_history
from ..helpers import parse_filterlog_entry
from ..models import PaginationOptions, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# 1. Diagnose Connectivity
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def diagnose_connectivity(
    host: str,
    count: int = 4,
) -> Dict:
    """Test connectivity to a host from the pfSense appliance.

    Runs ping, checks the ARP table for the target IP, and checks gateway
    status to give a combined connectivity diagnosis.

    Args:
        host: Hostname or IP address to test connectivity to
        count: Number of ping packets to send (default 4, max 20)
    """
    client = get_api_client()
    count = max(1, min(count, 20))
    results: Dict = {
        "success": True,
        "host": host,
        "ping": None,
        "arp_entry": None,
        "gateway_status": None,
        "issues": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # --- Ping ---
    try:
        ping_result = await client.crud_create(
            "/diagnostics/ping", {"host": host, "count": count}
        )
        ping_data = ping_result.get("data", ping_result)
        results["ping"] = ping_data

        # Detect ping failure from response text
        ping_text = str(ping_data)
        if "0 packets received" in ping_text or "100% packet loss" in ping_text.lower():
            results["issues"].append(
                f"Ping to {host} failed — 100% packet loss"
            )
    except Exception as e:
        logger.error("Ping diagnostic failed: %s", e)
        results["ping"] = {"error": str(e)}
        results["issues"].append(f"Ping failed: {e}")

    # --- ARP table lookup ---
    try:
        arp_result = await client.get_arp_table(
            filters=[QueryFilter("ip", host, "contains")]
        )
        arp_entries = arp_result.get("data") or []
        if arp_entries:
            results["arp_entry"] = arp_entries[0]
        else:
            results["arp_entry"] = None
            results["issues"].append(
                f"No ARP entry found for {host} — host may be unreachable at layer 2"
            )
    except Exception as e:
        logger.error("ARP lookup failed: %s", e)
        results["arp_entry"] = {"error": str(e)}

    # --- Gateway status ---
    try:
        gw_result = await client.crud_list("/routing/gateways")
        gateways = gw_result.get("data") or []
        gw_summary = []
        for gw in gateways:
            status = gw.get("status", "unknown")
            gw_summary.append({
                "name": gw.get("name"),
                "interface": gw.get("interface"),
                "gateway": gw.get("gateway"),
                "status": status,
                "monitor": gw.get("monitor"),
            })
            if status and status.lower() not in ("online", "none", ""):
                results["issues"].append(
                    f"Gateway {gw.get('name')} is {status}"
                )
        results["gateway_status"] = gw_summary
    except Exception as e:
        logger.error("Gateway status check failed: %s", e)
        results["gateway_status"] = {"error": str(e)}

    if not results["issues"]:
        results["diagnosis"] = f"Connectivity to {host} appears healthy"
    else:
        results["diagnosis"] = (
            f"Connectivity issues detected for {host}: "
            + "; ".join(results["issues"])
        )

    return results


# ---------------------------------------------------------------------------
# 2. Diagnose Blocked Traffic
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def diagnose_blocked_traffic(
    source_ip: str,
    destination_ip: Optional[str] = None,
    destination_port: Optional[str] = None,
    protocol: Optional[str] = None,
) -> Dict:
    """Comprehensive analysis of why traffic might be blocked.

    Searches firewall logs for the source IP, finds matching block/reject
    rules, checks alias memberships, and suggests fixes.

    Args:
        source_ip: Source IP address to investigate
        destination_ip: Optional destination IP to narrow the search
        destination_port: Optional destination port to narrow the search
        protocol: Optional protocol filter (tcp, udp, icmp)
    """
    client = get_api_client()
    results: Dict = {
        "success": True,
        "source_ip": source_ip,
        "destination_ip": destination_ip,
        "destination_port": destination_port,
        "protocol": protocol,
        "blocked_log_entries": [],
        "matching_block_rules": [],
        "alias_memberships": [],
        "suggestions": [],
        "issues": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # --- Search firewall logs for source IP ---
    try:
        log_result = await client.get_logs_by_ip(source_ip, lines=50)
        entries = log_result.get("data") or []
        blocked_entries = []
        for entry in entries:
            text = entry.get("text", "")
            parsed = parse_filterlog_entry(text)
            if parsed:
                is_block = parsed.get("action", "").lower() in ("block", "reject")
                matches_dst = (
                    not destination_ip or parsed.get("dst_ip") == destination_ip
                )
                matches_port = (
                    not destination_port
                    or parsed.get("dst_port") == str(destination_port)
                )
                matches_proto = (
                    not protocol
                    or parsed.get("protocol", "").lower() == protocol.lower()
                )
                if is_block and matches_dst and matches_port and matches_proto:
                    blocked_entries.append(parsed)
            else:
                # Fallback: raw text matching
                if "block" in text.lower() or "reject" in text.lower():
                    if source_ip in text:
                        blocked_entries.append({"raw": text})
        results["blocked_log_entries"] = blocked_entries[:20]
        if blocked_entries:
            results["issues"].append(
                f"Found {len(blocked_entries)} blocked log entries for {source_ip}"
            )
    except Exception as e:
        logger.error("Log search failed: %s", e)
        results["blocked_log_entries"] = [{"error": str(e)}]

    # --- Search firewall rules for block/reject rules matching source ---
    try:
        filters = [QueryFilter("type", "block|reject", "regex")]
        rules_result = await client.get_firewall_rules(filters=filters)
        all_block_rules = rules_result.get("data") or []

        matching_rules = []
        for rule in all_block_rules:
            src = str(rule.get("source", ""))
            dst = str(rule.get("destination", ""))
            dst_port = str(rule.get("destination_port", ""))
            # Check if rule could match the traffic
            source_match = (
                src == "any" or source_ip in src
            )
            dest_match = (
                not destination_ip
                or dst == "any"
                or destination_ip in dst
            )
            port_match = (
                not destination_port
                or not dst_port
                or dst_port == "any"
                or str(destination_port) in dst_port
            )
            if source_match and dest_match and port_match:
                matching_rules.append({
                    "id": rule.get("id"),
                    "type": rule.get("type"),
                    "interface": rule.get("interface"),
                    "source": rule.get("source"),
                    "destination": rule.get("destination"),
                    "destination_port": rule.get("destination_port"),
                    "protocol": rule.get("protocol"),
                    "descr": rule.get("descr"),
                    "disabled": rule.get("disabled", False),
                })
        results["matching_block_rules"] = matching_rules
        if matching_rules:
            results["issues"].append(
                f"Found {len(matching_rules)} block/reject rules that may match this traffic"
            )
    except Exception as e:
        logger.error("Rule search failed: %s", e)
        results["matching_block_rules"] = [{"error": str(e)}]

    # --- Check alias memberships ---
    try:
        alias_result = await client.find_aliases_containing_ip(source_ip)
        aliases = alias_result.get("data") or []
        alias_names = [
            {"name": a.get("name"), "type": a.get("type"), "descr": a.get("descr")}
            for a in aliases
        ]
        results["alias_memberships"] = alias_names
        if alias_names:
            results["issues"].append(
                f"Source IP {source_ip} is a member of aliases: "
                + ", ".join(a["name"] for a in alias_names)
            )
    except Exception as e:
        logger.error("Alias lookup failed: %s", e)
        results["alias_memberships"] = [{"error": str(e)}]

    # --- Build suggestions ---
    if results["matching_block_rules"]:
        for rule in results["matching_block_rules"]:
            if rule.get("disabled"):
                results["suggestions"].append(
                    f"Rule {rule.get('id')} ('{rule.get('descr')}') is a disabled "
                    f"block rule — it is NOT currently blocking traffic"
                )
            else:
                results["suggestions"].append(
                    f"Active block rule {rule.get('id')} ('{rule.get('descr')}') may "
                    f"be blocking this traffic. Consider disabling it or adding a pass "
                    f"rule above it."
                )
    if results["alias_memberships"]:
        results["suggestions"].append(
            f"Check if any of the aliases ({', '.join(a['name'] for a in results['alias_memberships'] if isinstance(a, dict) and 'name' in a)}) "
            f"are referenced in block rules."
        )
    if not results["blocked_log_entries"] and not results["matching_block_rules"]:
        results["suggestions"].append(
            "No obvious block rules or log entries found. Traffic may be blocked by "
            "a default deny rule, a floating rule, or the traffic may not be reaching "
            "pfSense at all. Check routing and interface assignments."
        )

    return results


# ---------------------------------------------------------------------------
# 3. Diagnose Interface Issues
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def diagnose_interface_issues(
    interface: str,
) -> Dict:
    """Analyze an interface for problems.

    Checks interface status, configuration, gateway status, and ARP entries
    on the specified interface.

    Args:
        interface: Interface name (e.g., "wan", "lan", "opt1")
    """
    client = get_api_client()
    results: Dict = {
        "success": True,
        "interface": interface,
        "link_status": None,
        "ip_config": None,
        "gateway_status": None,
        "arp_count": 0,
        "issues": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # --- Interface status ---
    try:
        iface_result = await client.get_interfaces()
        interfaces = iface_result.get("data") or []
        matched = None
        for iface in interfaces:
            if (iface.get("name", "").lower() == interface.lower()
                    or iface.get("if", "").lower() == interface.lower()
                    or iface.get("descr", "").lower() == interface.lower()):
                matched = iface
                break
        if matched:
            status = matched.get("status", "unknown")
            results["link_status"] = status
            results["ip_config"] = {
                "ipaddr": matched.get("ipaddr"),
                "subnet": matched.get("subnet"),
                "ipv6": matched.get("ipaddrv6"),
                "mac": matched.get("macaddr") or matched.get("hwif"),
                "media": matched.get("media"),
            }
            if status and status.lower() not in ("up", "active", "associated"):
                results["issues"].append(
                    f"Interface {interface} link status is '{status}' — may be down"
                )
            if not matched.get("ipaddr"):
                results["issues"].append(
                    f"Interface {interface} has no IPv4 address configured"
                )
        else:
            results["issues"].append(
                f"Interface '{interface}' not found in status output"
            )
    except Exception as e:
        logger.error("Interface status check failed: %s", e)
        results["link_status"] = {"error": str(e)}

    # --- Interface config ---
    try:
        config_result = await client.crud_list("/interfaces")
        configs = config_result.get("data") or []
        iface_config = None
        for cfg in configs:
            if (cfg.get("id", "").lower() == interface.lower()
                    or cfg.get("if", "").lower() == interface.lower()
                    or cfg.get("descr", "").lower() == interface.lower()):
                iface_config = cfg
                break
        results["interface_config"] = iface_config
        if iface_config and iface_config.get("enable") is False:
            results["issues"].append(
                f"Interface {interface} is disabled in configuration"
            )
    except Exception as e:
        logger.error("Interface config lookup failed: %s", e)
        results["interface_config"] = {"error": str(e)}

    # --- Gateway status for this interface ---
    try:
        gw_result = await client.crud_list("/routing/gateways")
        gateways = gw_result.get("data") or []
        iface_gateways = []
        for gw in gateways:
            gw_iface = gw.get("interface", "")
            if gw_iface.lower() == interface.lower():
                gw_info = {
                    "name": gw.get("name"),
                    "gateway": gw.get("gateway"),
                    "status": gw.get("status", "unknown"),
                    "monitor": gw.get("monitor"),
                }
                iface_gateways.append(gw_info)
                status = gw.get("status", "")
                if status and status.lower() not in ("online", "none", ""):
                    results["issues"].append(
                        f"Gateway {gw.get('name')} on {interface} is {status}"
                    )
        results["gateway_status"] = iface_gateways
    except Exception as e:
        logger.error("Gateway status check failed: %s", e)
        results["gateway_status"] = {"error": str(e)}

    # --- ARP entries on this interface ---
    try:
        arp_result = await client.get_arp_table(
            filters=[QueryFilter("interface", interface, "contains")]
        )
        arp_entries = arp_result.get("data") or []
        results["arp_count"] = len(arp_entries)
        if not arp_entries:
            results["issues"].append(
                f"No ARP entries on {interface} — no layer 2 neighbors detected"
            )
    except Exception as e:
        logger.error("ARP table check failed: %s", e)
        results["arp_count"] = {"error": str(e)}

    if not results["issues"]:
        results["diagnosis"] = f"Interface {interface} appears healthy"
    else:
        results["diagnosis"] = (
            f"Issues found on interface {interface}: "
            + "; ".join(results["issues"])
        )

    return results


# ---------------------------------------------------------------------------
# 4. Diagnose VPN Status
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def diagnose_vpn_status() -> Dict:
    """Comprehensive VPN health check across all VPN types.

    Gets status for OpenVPN servers, OpenVPN clients, IPsec SAs, and
    WireGuard peers. Returns per-VPN summary with connected/disconnected/error counts.
    """
    client = get_api_client()
    results: Dict = {
        "success": True,
        "openvpn_servers": None,
        "openvpn_clients": None,
        "ipsec_sas": None,
        "wireguard_peers": None,
        "summary": {},
        "issues": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # --- OpenVPN Servers ---
    try:
        ovpn_servers = await client.crud_get_settings("/status/openvpn/servers")
        servers_data = ovpn_servers.get("data") or []
        if isinstance(servers_data, dict):
            servers_data = [servers_data] if servers_data else []
        results["openvpn_servers"] = servers_data
        results["summary"]["openvpn_servers"] = {
            "total": len(servers_data),
        }
    except Exception as e:
        logger.error("OpenVPN server status failed: %s", e)
        results["openvpn_servers"] = {"error": str(e)}
        results["issues"].append(f"Failed to get OpenVPN server status: {e}")

    # --- OpenVPN Clients ---
    try:
        ovpn_clients = await client.crud_get_settings("/status/openvpn/clients")
        clients_data = ovpn_clients.get("data") or []
        if isinstance(clients_data, dict):
            clients_data = [clients_data] if clients_data else []
        connected = sum(
            1 for c in clients_data
            if isinstance(c, dict) and c.get("status", "").lower() in ("up", "connected", "running")
        )
        disconnected = len(clients_data) - connected
        results["openvpn_clients"] = clients_data
        results["summary"]["openvpn_clients"] = {
            "total": len(clients_data),
            "connected": connected,
            "disconnected": disconnected,
        }
        if disconnected > 0:
            results["issues"].append(
                f"{disconnected} OpenVPN client(s) are disconnected"
            )
    except Exception as e:
        logger.error("OpenVPN client status failed: %s", e)
        results["openvpn_clients"] = {"error": str(e)}
        results["issues"].append(f"Failed to get OpenVPN client status: {e}")

    # --- IPsec SAs ---
    try:
        ipsec_result = await client.crud_list("/status/ipsec/sas")
        sas_data = ipsec_result.get("data") or []
        established = sum(
            1 for sa in sas_data
            if isinstance(sa, dict) and sa.get("established")
        )
        results["ipsec_sas"] = sas_data
        results["summary"]["ipsec"] = {
            "total_sas": len(sas_data),
            "established": established,
            "not_established": len(sas_data) - established,
        }
        if sas_data and established < len(sas_data):
            results["issues"].append(
                f"{len(sas_data) - established} IPsec SA(s) not established"
            )
    except Exception as e:
        logger.error("IPsec SA status failed: %s", e)
        results["ipsec_sas"] = {"error": str(e)}
        results["issues"].append(f"Failed to get IPsec status: {e}")

    # --- WireGuard Peers ---
    try:
        wg_result = await client.crud_list("/vpn/wireguard/peers")
        peers_data = wg_result.get("data") or []
        results["wireguard_peers"] = peers_data
        results["summary"]["wireguard"] = {
            "total_peers": len(peers_data),
        }
    except Exception as e:
        # WireGuard may not be installed — not necessarily an issue
        logger.debug("WireGuard peer status failed (may not be installed): %s", e)
        results["wireguard_peers"] = {"note": "WireGuard may not be configured", "error": str(e)}
        results["summary"]["wireguard"] = {"total_peers": 0, "note": "not available"}

    if not results["issues"]:
        results["diagnosis"] = "All VPN tunnels appear healthy"
    else:
        results["diagnosis"] = (
            "VPN issues detected: " + "; ".join(results["issues"])
        )

    return results


# ---------------------------------------------------------------------------
# 5. Diagnose DHCP Issues
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def diagnose_dhcp_issues(
    interface: str = "lan",
    mac_address: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Dict:
    """Analyze DHCP service health on an interface.

    Checks DHCP server config, lease pool utilization, IP conflicts, and
    optionally looks up a specific MAC or IP address.

    Args:
        interface: Interface to check DHCP on (default "lan")
        mac_address: Optional MAC address to look up specific lease
        ip_address: Optional IP address to look up specific lease
    """
    client = get_api_client()
    results: Dict = {
        "success": True,
        "interface": interface,
        "dhcp_config": None,
        "pool_utilization": None,
        "conflicts": [],
        "specific_lease": None,
        "issues": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # --- DHCP server config ---
    pool_start = None
    pool_end = None
    try:
        dhcp_servers = await client.get_dhcp_servers()
        servers = dhcp_servers.get("data") or []
        matched_server = None
        for srv in servers:
            srv_iface = srv.get("interface") or srv.get("id") or ""
            if srv_iface.lower() == interface.lower():
                matched_server = srv
                break
        if matched_server:
            results["dhcp_config"] = {
                "enabled": matched_server.get("enable", False),
                "range_from": matched_server.get("range_from") or matched_server.get("range", {}).get("from"),
                "range_to": matched_server.get("range_to") or matched_server.get("range", {}).get("to"),
                "default_lease_time": matched_server.get("defaultleasetime"),
                "max_lease_time": matched_server.get("maxleasetime"),
                "domain": matched_server.get("domain"),
                "dns_servers": matched_server.get("dnsserver"),
                "gateway": matched_server.get("gateway"),
            }
            pool_start = results["dhcp_config"]["range_from"]
            pool_end = results["dhcp_config"]["range_to"]
            if not matched_server.get("enable", True):
                results["issues"].append(
                    f"DHCP server on {interface} is disabled"
                )
        else:
            results["issues"].append(
                f"No DHCP server configuration found for interface '{interface}'"
            )
    except Exception as e:
        logger.error("DHCP server config check failed: %s", e)
        results["dhcp_config"] = {"error": str(e)}

    # --- DHCP leases ---
    leases = []
    try:
        lease_result = await client.get_dhcp_leases(interface=interface)
        leases = lease_result.get("data") or []

        # Calculate pool utilization
        lease_count = len(leases)
        pool_size = None
        if pool_start and pool_end:
            try:
                start_parts = pool_start.split(".")
                end_parts = pool_end.split(".")
                start_num = int(start_parts[-1])
                end_num = int(end_parts[-1])
                # Simple estimation assuming same /24 subnet
                if start_parts[:3] == end_parts[:3]:
                    pool_size = end_num - start_num + 1
            except (ValueError, IndexError):
                pass

        results["pool_utilization"] = {
            "active_leases": lease_count,
            "pool_size": pool_size,
            "utilization_percent": (
                round((lease_count / pool_size) * 100, 1)
                if pool_size and pool_size > 0
                else None
            ),
        }

        if pool_size and lease_count >= pool_size:
            results["issues"].append(
                f"DHCP pool on {interface} is EXHAUSTED — "
                f"{lease_count} leases for pool size {pool_size}"
            )
        elif pool_size and lease_count >= pool_size * 0.9:
            results["issues"].append(
                f"DHCP pool on {interface} is nearly full — "
                f"{lease_count}/{pool_size} ({results['pool_utilization']['utilization_percent']}%)"
            )

        # Check for IP conflicts (same IP, different MAC)
        ip_to_macs: Dict[str, List[str]] = {}
        for lease in leases:
            lip = lease.get("ip") or lease.get("ipaddr") or ""
            lmac = lease.get("mac") or lease.get("hwaddr") or ""
            if lip:
                ip_to_macs.setdefault(lip, []).append(lmac)

        for lip, macs in ip_to_macs.items():
            unique_macs = set(m for m in macs if m)
            if len(unique_macs) > 1:
                results["conflicts"].append({
                    "ip": lip,
                    "macs": list(unique_macs),
                })
        if results["conflicts"]:
            results["issues"].append(
                f"Found {len(results['conflicts'])} IP conflict(s) — "
                "same IP assigned to different MACs"
            )

        # Look up specific lease
        if mac_address or ip_address:
            for lease in leases:
                lmac = (lease.get("mac") or lease.get("hwaddr") or "").lower()
                lip = lease.get("ip") or lease.get("ipaddr") or ""
                if mac_address and lmac == mac_address.lower():
                    results["specific_lease"] = lease
                    break
                if ip_address and lip == ip_address:
                    results["specific_lease"] = lease
                    break
            if not results["specific_lease"]:
                search_key = mac_address or ip_address
                results["issues"].append(
                    f"No active DHCP lease found for {search_key}"
                )
    except Exception as e:
        logger.error("DHCP lease check failed: %s", e)
        results["pool_utilization"] = {"error": str(e)}

    if not results["issues"]:
        results["diagnosis"] = f"DHCP service on {interface} appears healthy"
    else:
        results["diagnosis"] = (
            f"DHCP issues on {interface}: " + "; ".join(results["issues"])
        )

    return results


# ---------------------------------------------------------------------------
# 6. Diagnose DNS Resolution
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def diagnose_dns_resolution() -> Dict:
    """Check DNS resolver health.

    Gets DNS resolver settings, host/domain override counts, system DNS
    servers, and runs a connectivity check to verify upstream reachability.
    """
    client = get_api_client()
    results: Dict = {
        "success": True,
        "resolver_settings": None,
        "host_overrides_count": 0,
        "domain_overrides_count": 0,
        "system_dns_servers": None,
        "connectivity_check": None,
        "issues": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # --- DNS Resolver settings ---
    try:
        resolver = await client.crud_get_settings("/services/dns_resolver/settings")
        resolver_data = resolver.get("data", resolver)
        results["resolver_settings"] = {
            "enabled": resolver_data.get("enable", False) if isinstance(resolver_data, dict) else None,
            "forwarding_mode": resolver_data.get("forwarding", False) if isinstance(resolver_data, dict) else None,
            "dnssec": resolver_data.get("dnssec", False) if isinstance(resolver_data, dict) else None,
            "port": resolver_data.get("port") if isinstance(resolver_data, dict) else None,
        }
        if isinstance(resolver_data, dict) and not resolver_data.get("enable", True):
            results["issues"].append("DNS Resolver (Unbound) is disabled")
    except Exception as e:
        logger.error("DNS resolver settings check failed: %s", e)
        results["resolver_settings"] = {"error": str(e)}

    # --- Host overrides ---
    try:
        host_overrides = await client.crud_list("/services/dns_resolver/host_overrides")
        overrides = host_overrides.get("data") or []
        results["host_overrides_count"] = len(overrides)
    except Exception as e:
        logger.error("Host overrides check failed: %s", e)
        results["host_overrides_count"] = {"error": str(e)}

    # --- Domain overrides ---
    try:
        domain_overrides = await client.crud_list("/services/dns_resolver/domain_overrides")
        overrides = domain_overrides.get("data") or []
        results["domain_overrides_count"] = len(overrides)
    except Exception as e:
        logger.error("Domain overrides check failed: %s", e)
        results["domain_overrides_count"] = {"error": str(e)}

    # --- System DNS servers ---
    try:
        sys_status = await client.get_system_status()
        sys_data = sys_status.get("data", sys_status)
        if isinstance(sys_data, dict):
            dns_servers = sys_data.get("dns_servers") or sys_data.get("dnsserver") or []
            results["system_dns_servers"] = dns_servers
            if not dns_servers:
                results["issues"].append("No system DNS servers configured")
        else:
            results["system_dns_servers"] = None
    except Exception as e:
        logger.error("System DNS check failed: %s", e)
        results["system_dns_servers"] = {"error": str(e)}

    # --- Connectivity check (ping 8.8.8.8) ---
    try:
        ping_result = await client.crud_create(
            "/diagnostics/ping", {"host": "8.8.8.8", "count": 2}
        )
        ping_data = ping_result.get("data", ping_result)
        ping_text = str(ping_data)
        if "0 packets received" in ping_text or "100% packet loss" in ping_text.lower():
            results["connectivity_check"] = "FAILED"
            results["issues"].append(
                "Connectivity check to 8.8.8.8 failed — upstream DNS may be unreachable"
            )
        else:
            results["connectivity_check"] = "OK"
    except Exception as e:
        logger.error("DNS connectivity check failed: %s", e)
        results["connectivity_check"] = {"error": str(e)}
        results["issues"].append(f"Connectivity check failed: {e}")

    if not results["issues"]:
        results["diagnosis"] = "DNS resolver appears healthy"
    else:
        results["diagnosis"] = (
            "DNS issues detected: " + "; ".join(results["issues"])
        )

    return results


# ---------------------------------------------------------------------------
# 7. Diagnose Service Health
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def diagnose_service_health() -> Dict:
    """Comprehensive service health check.

    Gets all services and their status, identifies stopped services, and
    checks system resource utilization (CPU, memory, disk).
    """
    client = get_api_client()
    results: Dict = {
        "success": True,
        "services": None,
        "running_count": 0,
        "stopped_count": 0,
        "stopped_services": [],
        "system_resources": None,
        "issues": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # --- Service status ---
    try:
        svc_result = await client.get_services()
        services = svc_result.get("data") or []
        running = []
        stopped = []
        for svc in services:
            status = (svc.get("status") or "").lower()
            svc_info = {
                "name": svc.get("name"),
                "description": svc.get("description") or svc.get("descr"),
                "status": svc.get("status"),
            }
            if status in ("running", "active"):
                running.append(svc_info)
            else:
                stopped.append(svc_info)

        results["running_count"] = len(running)
        results["stopped_count"] = len(stopped)
        results["stopped_services"] = stopped
        results["services"] = {
            "running": [s["name"] for s in running],
            "stopped": [s["name"] for s in stopped],
        }

        # Known critical services that should typically be running
        critical_services = {"dhcpd", "unbound", "dpinger", "sshd", "syslogd"}
        for svc in stopped:
            svc_name = (svc.get("name") or "").lower()
            if svc_name in critical_services:
                results["issues"].append(
                    f"Critical service '{svc['name']}' is stopped"
                )
    except Exception as e:
        logger.error("Service status check failed: %s", e)
        results["services"] = {"error": str(e)}

    # --- System resources ---
    try:
        sys_status = await client.get_system_status()
        sys_data = sys_status.get("data", sys_status)
        if isinstance(sys_data, dict):
            results["system_resources"] = {
                "cpu_usage": sys_data.get("cpu_usage") or sys_data.get("cpu_load"),
                "memory_usage": sys_data.get("mem_usage") or sys_data.get("memory"),
                "disk_usage": sys_data.get("disk_usage") or sys_data.get("disk"),
                "uptime": sys_data.get("uptime"),
                "load_average": sys_data.get("load_avg") or sys_data.get("load_average"),
            }

            # Check high resource usage
            cpu = sys_data.get("cpu_usage") or sys_data.get("cpu_load")
            if cpu is not None:
                try:
                    cpu_val = float(str(cpu).rstrip("%"))
                    if cpu_val > 90:
                        results["issues"].append(
                            f"CPU usage is critically high: {cpu}%"
                        )
                    elif cpu_val > 75:
                        results["issues"].append(
                            f"CPU usage is elevated: {cpu}%"
                        )
                except (ValueError, TypeError):
                    pass

            mem = sys_data.get("mem_usage") or sys_data.get("memory")
            if mem is not None:
                try:
                    mem_val = float(str(mem).rstrip("%"))
                    if mem_val > 90:
                        results["issues"].append(
                            f"Memory usage is critically high: {mem}%"
                        )
                    elif mem_val > 80:
                        results["issues"].append(
                            f"Memory usage is elevated: {mem}%"
                        )
                except (ValueError, TypeError):
                    pass
        else:
            results["system_resources"] = sys_data
    except Exception as e:
        logger.error("System resource check failed: %s", e)
        results["system_resources"] = {"error": str(e)}

    if not results["issues"]:
        results["diagnosis"] = "All services and system resources appear healthy"
    else:
        results["diagnosis"] = (
            "Service/resource issues: " + "; ".join(results["issues"])
        )

    return results


# ---------------------------------------------------------------------------
# 8. Diagnose High Availability
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def diagnose_high_availability() -> Dict:
    """Check CARP/HA status if configured.

    Gets CARP status, virtual IPs, and checks if any CARP VIPs are in an
    unexpected state (e.g., backup when they should be master).
    """
    client = get_api_client()
    results: Dict = {
        "success": True,
        "carp_status": None,
        "virtual_ips": None,
        "carp_vip_summary": [],
        "issues": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # --- CARP status ---
    try:
        carp_result = await client.crud_get_settings("/status/carp")
        carp_data = carp_result.get("data", carp_result)
        results["carp_status"] = carp_data
        if isinstance(carp_data, dict):
            if carp_data.get("maintenance_mode"):
                results["issues"].append(
                    "CARP is in maintenance mode — all VIPs are in BACKUP state"
                )
            if not carp_data.get("enable", True):
                results["issues"].append("CARP is disabled")
    except Exception as e:
        logger.error("CARP status check failed: %s", e)
        results["carp_status"] = {"error": str(e)}
        results["issues"].append(f"Failed to get CARP status: {e}")

    # --- Virtual IPs ---
    try:
        vip_result = await client.crud_list("/firewall/virtual_ips")
        vips = vip_result.get("data") or []
        results["virtual_ips"] = vips

        carp_vips = []
        master_count = 0
        backup_count = 0
        init_count = 0
        for vip in vips:
            vip_mode = (vip.get("mode") or "").lower()
            if vip_mode == "carp":
                status = (vip.get("status") or vip.get("carpstatus") or "unknown").lower()
                vip_info = {
                    "subnet": vip.get("subnet"),
                    "interface": vip.get("interface"),
                    "vhid": vip.get("vhid"),
                    "status": status,
                    "descr": vip.get("descr"),
                }
                carp_vips.append(vip_info)
                if "master" in status:
                    master_count += 1
                elif "backup" in status:
                    backup_count += 1
                elif "init" in status:
                    init_count += 1

        results["carp_vip_summary"] = carp_vips
        results["carp_role_counts"] = {
            "master": master_count,
            "backup": backup_count,
            "init": init_count,
            "total": len(carp_vips),
        }

        # Warn if we have a mix of master and backup (split-brain potential)
        if master_count > 0 and backup_count > 0:
            results["issues"].append(
                f"Mixed CARP states detected: {master_count} MASTER, {backup_count} BACKUP — "
                f"possible split-brain or partial failover"
            )

        if init_count > 0:
            results["issues"].append(
                f"{init_count} CARP VIP(s) in INIT state — not yet negotiated"
            )

        if not carp_vips:
            results["issues"].append("No CARP virtual IPs configured")

    except Exception as e:
        logger.error("Virtual IP check failed: %s", e)
        results["virtual_ips"] = {"error": str(e)}

    if not results["issues"]:
        results["diagnosis"] = "CARP/HA appears healthy"
    else:
        results["diagnosis"] = (
            "HA issues detected: " + "; ".join(results["issues"])
        )

    return results


# ---------------------------------------------------------------------------
# 9. System Health Report
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_system_health_report() -> Dict:
    """Full system health dashboard — combines all diagnostics into one report.

    Checks system status, interface health, service status, gateway status,
    VPN status, DHCP utilization, recent blocked traffic, and firewall rule
    counts. Returns severity-coded findings.
    """
    client = get_api_client()
    report: Dict = {
        "success": True,
        "system_status": None,
        "interfaces": None,
        "services": None,
        "gateways": None,
        "vpn_summary": None,
        "dhcp_summary": None,
        "blocked_traffic_count": 0,
        "firewall_rule_count": 0,
        "findings": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # --- System status ---
    try:
        sys_status = await client.get_system_status()
        sys_data = sys_status.get("data", sys_status)
        report["system_status"] = {
            "cpu_usage": sys_data.get("cpu_usage") or sys_data.get("cpu_load") if isinstance(sys_data, dict) else None,
            "memory_usage": sys_data.get("mem_usage") or sys_data.get("memory") if isinstance(sys_data, dict) else None,
            "disk_usage": sys_data.get("disk_usage") or sys_data.get("disk") if isinstance(sys_data, dict) else None,
            "uptime": sys_data.get("uptime") if isinstance(sys_data, dict) else None,
            "version": sys_data.get("system_version") or sys_data.get("version") if isinstance(sys_data, dict) else None,
        }
        # Check resource levels
        if isinstance(sys_data, dict):
            for metric, label in [
                ("cpu_usage", "CPU"), ("cpu_load", "CPU"),
                ("mem_usage", "Memory"), ("memory", "Memory"),
            ]:
                val = sys_data.get(metric)
                if val is not None:
                    try:
                        num = float(str(val).rstrip("%"))
                        if num > 90:
                            report["findings"].append({
                                "severity": "critical",
                                "component": "system",
                                "message": f"{label} usage critically high: {val}%",
                            })
                        elif num > 75:
                            report["findings"].append({
                                "severity": "warning",
                                "component": "system",
                                "message": f"{label} usage elevated: {val}%",
                            })
                        break  # Only report the first matching metric per type
                    except (ValueError, TypeError):
                        pass
    except Exception as e:
        logger.error("System status check failed: %s", e)
        report["system_status"] = {"error": str(e)}
        report["findings"].append({
            "severity": "error",
            "component": "system",
            "message": f"Failed to get system status: {e}",
        })

    # --- Interface status ---
    try:
        iface_result = await client.get_interfaces()
        interfaces = iface_result.get("data") or []
        iface_summary = []
        for iface in interfaces:
            status = iface.get("status", "unknown")
            info = {
                "name": iface.get("name") or iface.get("descr"),
                "status": status,
                "ipaddr": iface.get("ipaddr"),
            }
            iface_summary.append(info)
            if status and status.lower() not in ("up", "active", "associated", "no carrier"):
                report["findings"].append({
                    "severity": "warning",
                    "component": "interface",
                    "message": f"Interface {info['name']} status: {status}",
                })
        report["interfaces"] = iface_summary
    except Exception as e:
        logger.error("Interface check failed: %s", e)
        report["interfaces"] = {"error": str(e)}

    # --- Service health ---
    try:
        svc_result = await client.get_services()
        services = svc_result.get("data") or []
        running = 0
        stopped_list = []
        for svc in services:
            status = (svc.get("status") or "").lower()
            if status in ("running", "active"):
                running += 1
            else:
                stopped_list.append(svc.get("name"))

        report["services"] = {
            "running": running,
            "stopped": len(stopped_list),
            "stopped_names": stopped_list,
        }

        critical = {"dhcpd", "unbound", "dpinger", "sshd"}
        for svc_name in stopped_list:
            if (svc_name or "").lower() in critical:
                report["findings"].append({
                    "severity": "critical",
                    "component": "service",
                    "message": f"Critical service '{svc_name}' is stopped",
                })
    except Exception as e:
        logger.error("Service check failed: %s", e)
        report["services"] = {"error": str(e)}

    # --- Gateway status ---
    try:
        gw_result = await client.crud_list("/routing/gateways")
        gateways = gw_result.get("data") or []
        gw_summary = []
        for gw in gateways:
            status = gw.get("status", "unknown")
            gw_summary.append({
                "name": gw.get("name"),
                "status": status,
                "interface": gw.get("interface"),
            })
            if status and status.lower() not in ("online", "none", ""):
                report["findings"].append({
                    "severity": "warning",
                    "component": "gateway",
                    "message": f"Gateway {gw.get('name')} is {status}",
                })
        report["gateways"] = gw_summary
    except Exception as e:
        logger.error("Gateway check failed: %s", e)
        report["gateways"] = {"error": str(e)}

    # --- VPN summary ---
    try:
        vpn_info = {}
        try:
            ovpn_s = await client.crud_get_settings("/status/openvpn/servers")
            s_data = ovpn_s.get("data") or []
            if isinstance(s_data, dict):
                s_data = [s_data] if s_data else []
            vpn_info["openvpn_servers"] = len(s_data)
        except Exception:
            vpn_info["openvpn_servers"] = "unavailable"

        try:
            ovpn_c = await client.crud_get_settings("/status/openvpn/clients")
            c_data = ovpn_c.get("data") or []
            if isinstance(c_data, dict):
                c_data = [c_data] if c_data else []
            vpn_info["openvpn_clients"] = len(c_data)
            disconnected = sum(
                1 for c in c_data
                if isinstance(c, dict) and c.get("status", "").lower() not in ("up", "connected", "running")
            )
            if disconnected > 0:
                report["findings"].append({
                    "severity": "warning",
                    "component": "vpn",
                    "message": f"{disconnected} OpenVPN client(s) disconnected",
                })
        except Exception:
            vpn_info["openvpn_clients"] = "unavailable"

        try:
            ipsec_r = await client.crud_list("/status/ipsec/sas")
            ipsec_data = ipsec_r.get("data") or []
            vpn_info["ipsec_sas"] = len(ipsec_data)
        except Exception:
            vpn_info["ipsec_sas"] = "unavailable"

        report["vpn_summary"] = vpn_info
    except Exception as e:
        logger.error("VPN summary check failed: %s", e)
        report["vpn_summary"] = {"error": str(e)}

    # --- DHCP utilization ---
    try:
        lease_result = await client.get_dhcp_leases()
        leases = lease_result.get("data") or []
        report["dhcp_summary"] = {
            "total_active_leases": len(leases),
        }
    except Exception as e:
        logger.error("DHCP check failed: %s", e)
        report["dhcp_summary"] = {"error": str(e)}

    # --- Recent blocked traffic count ---
    try:
        blocked_result = await client.get_blocked_traffic_logs(lines=50)
        blocked_entries = blocked_result.get("data") or []
        report["blocked_traffic_count"] = len(blocked_entries)
        if len(blocked_entries) >= 50:
            report["findings"].append({
                "severity": "info",
                "component": "firewall",
                "message": "50+ blocked traffic entries in recent logs — review for anomalies",
            })
    except Exception as e:
        logger.error("Blocked traffic check failed: %s", e)
        report["blocked_traffic_count"] = {"error": str(e)}

    # --- Firewall rule count ---
    try:
        rules_result = await client.get_firewall_rules()
        rules = rules_result.get("data") or []
        report["firewall_rule_count"] = len(rules)
    except Exception as e:
        logger.error("Firewall rule count failed: %s", e)
        report["firewall_rule_count"] = {"error": str(e)}

    # --- Overall health assessment ---
    critical_count = sum(1 for f in report["findings"] if f.get("severity") == "critical")
    warning_count = sum(1 for f in report["findings"] if f.get("severity") == "warning")
    error_count = sum(1 for f in report["findings"] if f.get("severity") == "error")

    if critical_count > 0:
        report["overall_health"] = "CRITICAL"
    elif error_count > 0 or warning_count > 2:
        report["overall_health"] = "DEGRADED"
    elif warning_count > 0:
        report["overall_health"] = "WARNING"
    else:
        report["overall_health"] = "HEALTHY"

    report["finding_counts"] = {
        "critical": critical_count,
        "warning": warning_count,
        "error": error_count,
        "info": sum(1 for f in report["findings"] if f.get("severity") == "info"),
    }

    return report


# ---------------------------------------------------------------------------
# 10. Search Audit Trail
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_audit_trail(
    limit: int = 20,
    tool_filter: Optional[str] = None,
    risk_filter: Optional[str] = None,
) -> Dict:
    """Search the guardrail audit log for recent destructive actions taken.

    Checks the in-memory rollback history and, if MCP_AUDIT_LOG is configured,
    reads recent entries from the audit log file.

    Args:
        limit: Maximum number of entries to return (default 20)
        tool_filter: Optional filter by tool name (substring match)
        risk_filter: Optional filter by risk level (read, low, medium, high, critical)
    """
    limit = max(1, min(limit, 100))
    results: Dict = {
        "success": True,
        "rollback_history": [],
        "audit_log_entries": [],
        "audit_log_configured": False,
        "issues": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # --- In-memory rollback history ---
    try:
        rollback_entries = get_rollback_history(limit=limit)
        if tool_filter:
            rollback_entries = [
                e for e in rollback_entries
                if tool_filter.lower() in (e.get("tool") or "").lower()
            ]
        results["rollback_history"] = rollback_entries
    except Exception as e:
        logger.error("Failed to get rollback history: %s", e)
        results["rollback_history"] = [{"error": str(e)}]

    # --- File-based audit log ---
    audit_log_path = os.getenv("MCP_AUDIT_LOG", "")
    results["audit_log_configured"] = bool(audit_log_path)

    if audit_log_path:
        try:
            if os.path.isfile(audit_log_path):
                with open(audit_log_path, "r") as f:
                    lines = f.readlines()

                # Read the last N lines
                recent_lines = lines[-limit * 2:]  # Read extra to account for filtering
                entries = []
                for line in recent_lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        # Apply filters
                        if tool_filter:
                            if tool_filter.lower() not in (entry.get("tool") or "").lower():
                                continue
                        if risk_filter:
                            if (entry.get("risk_level") or "").lower() != risk_filter.lower():
                                continue
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue

                results["audit_log_entries"] = entries[-limit:]
            else:
                results["issues"].append(
                    f"Audit log file not found at: {audit_log_path}"
                )
        except Exception as e:
            logger.error("Failed to read audit log: %s", e)
            results["audit_log_entries"] = [{"error": str(e)}]
    else:
        results["issues"].append(
            "MCP_AUDIT_LOG is not configured — file-based audit logging is disabled. "
            "Set MCP_AUDIT_LOG=/path/to/audit.log to enable."
        )

    total_entries = len(results["rollback_history"]) + len(results["audit_log_entries"])
    results["total_entries"] = total_entries

    if total_entries == 0:
        results["diagnosis"] = "No destructive actions found in audit trail"
    else:
        results["diagnosis"] = (
            f"Found {total_entries} audit entries "
            f"({len(results['rollback_history'])} rollback, "
            f"{len(results['audit_log_entries'])} audit log)"
        )

    return results
