"""Log analysis tools for pfSense MCP server."""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from ..models import PaginationOptions, QueryFilter
from ..server import get_api_client, logger, mcp

# Allowlist of valid pfSense log types to prevent path traversal
_VALID_LOG_TYPES = {"firewall", "system", "dhcp", "vpn", "gateways", "resolver", "portalauth"}


@mcp.tool()
async def get_firewall_log(
    lines: int = 20,
    action_filter: Optional[str] = None,
    interface: Optional[str] = None,
    source_ip: Optional[str] = None,
    destination_ip: Optional[str] = None,
    destination_port: Optional[str] = None,
    protocol: Optional[str] = None,
) -> Dict:
    """Get firewall log entries with optional filtering

    Args:
        lines: Number of log lines to retrieve (default 20, max 50)
        action_filter: Filter by action (pass, block, reject)
        interface: Filter by interface (wan, lan, etc.)
        source_ip: Filter by source IP address
        destination_ip: Filter by destination IP address
        destination_port: Filter by destination port
        protocol: Filter by protocol (tcp, udp, icmp)
    """
    client = get_api_client()
    try:
        filters = []

        if action_filter:
            filters.append(QueryFilter("action", action_filter))
        if interface:
            filters.append(QueryFilter("interface", interface))
        if source_ip:
            filters.append(QueryFilter("src_ip", source_ip))
        if destination_ip:
            filters.append(QueryFilter("dst_ip", destination_ip))
        if destination_port:
            filters.append(QueryFilter("dst_port", destination_port))
        if protocol:
            filters.append(QueryFilter("protocol", protocol))

        # Log endpoints don't support sort_by — logs are returned in
        # reverse chronological order by pfSense already
        safe_lines = max(1, min(lines, 50))
        logs = await client.get_firewall_logs(
            lines=safe_lines,
            filters=filters if filters else None,
        )

        return {
            "success": True,
            "lines_requested": safe_lines,
            "filters_applied": {
                "action": action_filter,
                "interface": interface,
                "source_ip": source_ip,
                "destination_ip": destination_ip,
                "destination_port": destination_port,
                "protocol": protocol,
            },
            "count": len(logs.get("data", [])),
            "log_entries": logs.get("data", []),
            "links": client.extract_links(logs),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get firewall log: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def analyze_blocked_traffic(
    hours_back: int = 24,
    limit: int = 20,
    group_by_source: bool = True
) -> Dict:
    """Analyze blocked traffic patterns from firewall logs

    Args:
        hours_back: How many hours back to analyze
        limit: Maximum number of log entries to analyze
        group_by_source: Whether to group results by source IP
    """
    client = get_api_client()
    try:
        # Get blocked traffic logs (already reverse-chronological)
        safe_limit = max(1, min(limit, 50))
        logs = await client.get_blocked_traffic_logs(lines=safe_limit)

        log_data = logs.get("data", [])

        # Filter by hours_back if timestamps are available
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        cutoff_str = cutoff.isoformat()
        log_data = [
            entry for entry in log_data
            if not entry.get("timestamp") or entry["timestamp"] >= cutoff_str
        ]

        if group_by_source:
            # Group by source IP
            source_stats = {}
            for entry in log_data:
                src_ip = entry.get("src_ip", "unknown")
                if src_ip not in source_stats:
                    source_stats[src_ip] = {
                        "count": 0,
                        "ports": set(),
                        "destinations": set(),
                        "latest_time": None
                    }

                source_stats[src_ip]["count"] += 1

                if entry.get("dst_port"):
                    source_stats[src_ip]["ports"].add(entry["dst_port"])

                if entry.get("dst_ip"):
                    source_stats[src_ip]["destinations"].add(entry["dst_ip"])

                if entry.get("timestamp"):
                    current = source_stats[src_ip]["latest_time"]
                    if current is None or entry["timestamp"] > current:
                        source_stats[src_ip]["latest_time"] = entry["timestamp"]

            # Convert sets to lists for JSON serialization
            for ip, stats in source_stats.items():
                stats["ports"] = list(stats["ports"])
                stats["destinations"] = list(stats["destinations"])
                stats["threat_score"] = min(10, stats["count"] / 10)

            # Sort by count
            sorted_sources = sorted(
                source_stats.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )

            analysis = {
                "grouped_by": "source_ip",
                "total_unique_sources": len(source_stats),
                "top_sources": dict(sorted_sources[:20])
            }
        else:
            analysis = {
                "grouped_by": "none",
                "raw_entries": log_data
            }

        return {
            "success": True,
            "analysis_period_hours": hours_back,
            "total_entries_analyzed": len(log_data),
            "analysis": analysis,
            "links": client.extract_links(logs),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to analyze blocked traffic: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def search_logs_by_ip(
    ip_address: str,
    log_type: str = "firewall",
    lines: int = 50,
) -> Dict:
    """Search logs for activity related to a specific IP address

    Args:
        ip_address: IP address to search for
        log_type: Type of logs to search (firewall, system, etc.)
        lines: Number of log lines to retrieve (default 50, max 50)
    """
    client = get_api_client()
    try:
        safe_lines = max(1, min(lines, 50))
        if log_type == "firewall":
            # Search both source and destination IPs, merge results
            src_logs = await client.get_logs_by_ip(ip_address, safe_lines)
            dst_filters = [QueryFilter("dst_ip", ip_address)]
            dst_logs = await client.get_firewall_logs(
                lines=safe_lines, filters=dst_filters
            )
            # Merge and deduplicate (use timestamp+src_ip+dst_ip as key)
            seen = set()
            merged = []
            for entry in src_logs.get("data", []) + dst_logs.get("data", []):
                key = (entry.get("timestamp"), entry.get("src_ip"), entry.get("dst_ip"), entry.get("dst_port"))
                if key not in seen:
                    seen.add(key)
                    merged.append(entry)
            # Sort by timestamp descending before truncating to keep most recent
            merged.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
            logs = src_logs  # preserve links/metadata from first response
            logs["data"] = merged[:safe_lines]
        else:
            # Validate log_type against allowlist to prevent path traversal
            if log_type not in _VALID_LOG_TYPES:
                return {
                    "success": False,
                    "error": f"Invalid log_type '{log_type}'. Must be one of: {', '.join(sorted(_VALID_LOG_TYPES))}",
                }
            # For other log types, use general log search
            filters = [QueryFilter("message", ip_address, "contains")]
            logs = await client._make_request(
                "GET", f"/diagnostics/log/{log_type}",
                filters=filters,
                pagination=PaginationOptions(limit=safe_lines)
            )

        log_entries = logs.get("data", [])

        # Analyze patterns if firewall logs
        if log_type == "firewall" and log_entries:
            patterns = {
                "total_entries": len(log_entries),
                "blocked_count": 0,
                "allowed_count": 0,
                "ports_accessed": set(),
                "protocols_used": set()
            }

            for entry in log_entries:
                action = entry.get("action", "").lower()
                if "block" in action or "reject" in action:
                    patterns["blocked_count"] += 1
                elif "pass" in action or "allow" in action:
                    patterns["allowed_count"] += 1

                if entry.get("dst_port"):
                    patterns["ports_accessed"].add(entry["dst_port"])

                if entry.get("protocol"):
                    patterns["protocols_used"].add(entry["protocol"])

            # Convert sets to lists
            patterns["ports_accessed"] = list(patterns["ports_accessed"])
            patterns["protocols_used"] = list(patterns["protocols_used"])
        else:
            patterns = None

        return {
            "success": True,
            "ip_address": ip_address,
            "log_type": log_type,
            "total_entries": len(log_entries),
            "patterns": patterns,
            "log_entries": log_entries,
            "links": client.extract_links(logs),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to search logs by IP: {e}")
        return {"success": False, "error": str(e)}
