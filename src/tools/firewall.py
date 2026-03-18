"""Firewall tools for pfSense MCP server."""

import ipaddress
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from ..helpers import (
    create_default_sort,
    create_interface_filter,
    create_pagination,
    create_port_filter,
    validate_port_value,
)
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp


@mcp.tool()
async def search_firewall_rules(
    interface: Optional[str] = None,
    source_ip: Optional[str] = None,
    destination_port: Optional[Union[int, str]] = None,
    rule_type: Optional[str] = None,
    search_description: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "tracker"
) -> Dict:
    """Search firewall rules with advanced filtering and pagination

    Args:
        interface: Filter by interface (wan, lan, etc.)
        source_ip: Filter by source IP (supports partial matching)
        destination_port: Filter by destination port
        rule_type: Filter by rule type (pass, block, reject)
        search_description: Search in rule descriptions
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (tracker, interface, type, descr, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if interface:
            filters.append(create_interface_filter(interface))

        if source_ip:
            filters.append(QueryFilter("source", source_ip, "contains"))

        if destination_port:
            filters.append(create_port_filter(destination_port))

        if rule_type:
            filters.append(QueryFilter("type", rule_type))

        if search_description:
            filters.append(QueryFilter("descr", search_description, "contains"))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        rules = await client.get_firewall_rules(
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "interface": interface,
                "source_ip": source_ip,
                "destination_port": destination_port,
                "rule_type": rule_type,
                "search_description": search_description
            },
            "count": len(rules.get("data") or []),
            "rules": rules.get("data") or [],
            "links": client.extract_links(rules),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to search firewall rules: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def find_blocked_rules(
    interface: Optional[str] = None,
) -> Dict:
    """Find all firewall rules that block or reject traffic

    Args:
        interface: Optional interface filter (wan, lan, etc.)
    """
    client = get_api_client()
    try:
        rules = await client.find_blocked_rules()

        # Apply interface filter if specified
        # interface field is a list (e.g. ["wan"]), so use 'in' not '=='
        if interface:
            rules["data"] = [
                rule for rule in rules.get("data") or []
                if interface in (rule.get("interface") or [])
            ]

        return {
            "success": True,
            "interface_filter": interface,
            "count": len(rules.get("data") or []),
            "blocked_rules": rules.get("data") or [],
            "links": client.extract_links(rules),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to find blocked rules: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def create_firewall_rule_advanced(
    interface: str,
    rule_type: str,
    protocol: str,
    source: str,
    destination: str,
    description: Optional[str] = None,
    destination_port: Optional[str] = None,
    position: Optional[int] = None,
    apply_immediately: bool = True,
    log_matches: bool = True
) -> Dict:
    """Create a firewall rule with advanced placement and control options

    Args:
        interface: Interface for the rule (wan, lan, etc.)
        rule_type: Rule type (pass, block, reject)
        protocol: Protocol (tcp, udp, icmp, any)
        source: Source address (any, IP, network, alias name)
        destination: Destination address (any, IP, network, alias name)
        description: Optional rule description
        destination_port: Single port (443), range (1024-65535), or alias name (MyPorts). Do NOT pass multiple space/comma-separated ports — create a port alias first instead.
        position: Optional position to insert rule (0 = top)
        apply_immediately: Whether to apply changes immediately
        log_matches: Whether to log rule matches
    """
    client = get_api_client()

    # Validate port format before sending to API
    if destination_port:
        port_error = validate_port_value(destination_port, "destination_port")
        if port_error:
            return {"success": False, "error": port_error}

    rule_data = {
        "interface": [interface] if isinstance(interface, str) else interface,
        "type": rule_type,
        "ipprotocol": "inet",
        "source": source,
        "destination": destination,
        "descr": description or f"Created via Enhanced MCP at {datetime.now(timezone.utc).isoformat()}",
        "log": log_matches,
        "statetype": "keep state",  # Required for pf filter compiler
    }

    # Handle protocol field - try null for "any", otherwise use the specified protocol
    if protocol and protocol.lower() == "any":
        rule_data["protocol"] = None  # Try null for "any protocol"
    elif protocol:
        rule_data["protocol"] = protocol

    if destination_port:
        rule_data["destination_port"] = destination_port

    # Create rule without placement (placement on POST is unreliable);
    # we'll move it afterward if a position was requested
    control = ControlParameters(
        apply=apply_immediately if position is None else False,
    )

    try:
        result = await client.create_firewall_rule(rule_data, control)

        # If a specific position was requested, move the rule there
        if position is not None:
            new_rule_id = result.get("data", {}).get("id")
            if new_rule_id is not None:
                await client.move_firewall_rule(
                    new_rule_id, position, apply_immediately=False
                )
            else:
                logger.warning("Rule created but ID not returned — cannot move to position %d", position)
            # Apply after create+move (create was deferred above when position is set)
            if apply_immediately:
                await client.apply_firewall_changes()

        return {
            "success": True,
            "message": "Firewall rule created with advanced options",
            "rule": result.get("data", result),
            "applied_immediately": apply_immediately,
            "position": position,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to create advanced firewall rule: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def move_firewall_rule(
    rule_id: int,
    new_position: int,
    apply_immediately: bool = True
) -> Dict:
    """Move a firewall rule to a new position in the rule order

    Args:
        rule_id: Rule ID (array index from search_firewall_rules, e.g., 0, 1, 2...)
        new_position: New position (0 = top, higher numbers = lower priority)
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        result = await client.move_firewall_rule(
            rule_id, new_position, apply_immediately=False
        )

        # The PATCH ?apply=true doesn't reliably trigger filter_configure,
        # so explicitly apply to ensure the compiled ruleset is updated
        if apply_immediately:
            await client.apply_firewall_changes()

        return {
            "success": True,
            "message": f"Rule {rule_id} moved to position {new_position}",
            "rule_id": rule_id,
            "new_position": new_position,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to move firewall rule: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def update_firewall_rule(
    rule_id: int,
    rule_type: Optional[str] = None,
    interface: Optional[str] = None,
    protocol: Optional[str] = None,
    source: Optional[str] = None,
    destination: Optional[str] = None,
    source_port: Optional[str] = None,
    destination_port: Optional[str] = None,
    description: Optional[str] = None,
    disabled: Optional[bool] = None,
    log_matches: Optional[bool] = None,
    apply_immediately: bool = True
) -> Dict:
    """Update an existing firewall rule by ID

    Args:
        rule_id: Rule ID (array index from search_firewall_rules, e.g., 0, 1, 2...)
        rule_type: Rule type (pass, block, reject)
        interface: Interface for the rule (wan, lan, etc.)
        protocol: Protocol (tcp, udp, icmp, any)
        source: Source address (any, IP, network, alias name)
        destination: Destination address (any, IP, network, alias name)
        source_port: Single port (443), range (1024-65535), or alias name
        destination_port: Single port (443), range (1024-65535), or alias name. Do NOT pass multiple space/comma-separated ports — create a port alias first instead.
        description: Rule description
        disabled: Whether the rule is disabled
        log_matches: Whether to log rule matches
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        # Validate port formats before sending to API
        for port_param, port_val in [("source_port", source_port), ("destination_port", destination_port)]:
            if port_val:
                port_error = validate_port_value(port_val, port_param)
                if port_error:
                    return {"success": False, "error": port_error}

        # Map Python parameter names to pfSense API field names
        field_map = {
            "rule_type": "type",
            "interface": "interface",
            "protocol": "protocol",
            "source": "source",
            "destination": "destination",
            "source_port": "source_port",
            "destination_port": "destination_port",
            "description": "descr",
            "disabled": "disabled",
            "log_matches": "log",
        }

        params = {
            "rule_type": rule_type,
            "interface": interface,
            "protocol": protocol,
            "source": source,
            "destination": destination,
            "source_port": source_port,
            "destination_port": destination_port,
            "description": description,
            "disabled": disabled,
            "log_matches": log_matches,
        }

        updates = {}
        for param_name, value in params.items():
            if value is not None:
                api_field = field_map[param_name]
                if param_name == "interface":
                    updates[api_field] = [value] if isinstance(value, str) else value
                elif param_name == "protocol" and isinstance(value, str) and value.lower() == "any":
                    updates[api_field] = None
                else:
                    updates[api_field] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.update_firewall_rule(rule_id, updates, control)

        return {
            "success": True,
            "message": f"Firewall rule {rule_id} updated",
            "rule_id": rule_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to update firewall rule: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def delete_firewall_rule(
    rule_id: int,
    apply_immediately: bool = True
) -> Dict:
    """Delete a firewall rule by ID

    Args:
        rule_id: Rule ID (array index from search_firewall_rules, e.g., 0, 1, 2...)
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        result = await client.delete_firewall_rule(rule_id, apply_immediately)

        return {
            "success": True,
            "message": f"Firewall rule {rule_id} deleted",
            "rule_id": rule_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to delete firewall rule: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def bulk_block_ips(
    ip_addresses: List[str],
    interface: str = "wan",
    description_prefix: str = "Bulk block via MCP"
) -> Dict:
    """Block multiple IP addresses at once

    Args:
        ip_addresses: List of IP addresses to block
        interface: Interface to apply blocks on
        description_prefix: Prefix for rule descriptions
    """
    client = get_api_client()
    results = []
    errors = []

    for ip in ip_addresses:
        # Validate IP/network before making API call
        try:
            ipaddress.ip_network(ip, strict=False)
        except ValueError:
            logger.error(f"Invalid IP address/network: {ip}")
            errors.append({"ip": ip, "error": f"Invalid IP address or network: {ip}"})
            continue

        try:
            rule_data = {
                "interface": [interface] if isinstance(interface, str) else interface,
                "type": "block",
                "ipprotocol": "inet",
                "protocol": None,  # null = any protocol
                "source": ip,
                "destination": "any",
                "descr": f"{description_prefix}: {ip}",
                "log": True,
                "statetype": "keep state",
            }

            # Don't apply immediately for bulk operations
            control = ControlParameters(apply=False)
            result = await client.create_firewall_rule(rule_data, control)
            results.append({"ip": ip, "success": True, "rule_id": result.get("data", {}).get("id")})

        except Exception as e:
            logger.error(f"Failed to block IP {ip}: {e}")
            errors.append({"ip": ip, "error": str(e)})

    # Apply all changes at once
    if results:
        try:
            await client.apply_firewall_changes()
            applied = True
        except Exception as e:
            applied = False
            logger.error(f"Failed to apply bulk changes: {e}")
    else:
        applied = False

    return {
        "success": len(results) > 0,
        "total_requested": len(ip_addresses),
        "successful": len(results),
        "failed": len(errors),
        "applied": applied,
        "results": results,
        "errors": errors,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@mcp.tool()
async def apply_firewall_changes() -> Dict:
    """Force apply pending firewall changes and recompile the pf ruleset.

    Use this after any firewall config change to ensure the compiled ruleset
    (/tmp/rules.debug) matches the configuration. The apply_immediately
    parameter on other tools doesn't always trigger full recompilation.
    """
    client = get_api_client()
    try:
        result = await client.apply_firewall_changes()

        return {
            "success": True,
            "message": "Firewall changes applied and filter ruleset recompiled",
            "result": result.get("data", result),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to apply firewall changes: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_pf_rules() -> Dict:
    """Read the compiled pf ruleset (/tmp/rules.debug) to verify what pf is
    actually enforcing vs what's in config.xml.

    Returns the raw compiled rules that the packet filter is using.
    """
    client = get_api_client()
    try:
        result = await client.run_diagnostic_command("cat /tmp/rules.debug")

        return {
            "success": True,
            "compiled_rules": result.get("data", result),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to read compiled rules: {e}")
        return {"success": False, "error": str(e)}
