"""Log analysis tools for pfSense MCP server."""

import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from ..models import QueryFilter
from ..server import get_api_client, logger, mcp

# Allowlist of valid pfSense REST API v2 log endpoints.
# These map to actual endpoints at /api/v2/status/logs/<type>
# Note: "vpn" is "openvpn", "portalauth" is "auth" in the API
_VALID_LOG_TYPES = {"firewall", "system", "dhcp", "openvpn", "auth"}


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse a timestamp string to a timezone-aware datetime (assumes UTC if naive)."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # Assume UTC if no timezone info present
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


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
        # The pfSense firewall log model only has a single 'text' field
        # containing the raw log line. We can only filter on text__contains
        # server-side, then do further filtering client-side.
        filters = []

        # Build a text-based server-side filter from the most specific param
        text_search = source_ip or destination_ip or destination_port or action_filter
        if text_search:
            filters.append(QueryFilter("text", text_search, "contains"))

        # Log endpoints don't support sort_by — logs are returned in
        # reverse chronological order by pfSense already
        safe_lines = max(1, min(lines, 50))
        logs = await client.get_firewall_logs(
            lines=safe_lines,
            filters=filters if filters else None,
        )

        # Client-side filtering on the raw text lines for remaining params
        entries = logs.get("data", [])
        if entries:
            def _matches(entry):
                text = entry.get("text", "")
                if action_filter and action_filter.lower() not in text.lower():
                    return False
                if interface and interface.lower() not in text.lower():
                    return False
                if source_ip and source_ip not in text:
                    return False
                if destination_ip and destination_ip not in text:
                    return False
                if destination_port and destination_port not in text:
                    return False
                if protocol and protocol.lower() not in text.lower():
                    return False
                return True
            entries = [e for e in entries if _matches(e)]
            logs["data"] = entries

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

        # Filter by hours_back using parsed timestamps
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        log_data = [
            entry for entry in log_data
            if (ts := _parse_timestamp(entry.get("timestamp"))) is None or ts >= cutoff
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

                ts = _parse_timestamp(entry.get("timestamp"))
                if ts:
                    current = _parse_timestamp(source_stats[src_ip]["latest_time"])
                    if current is None or ts > current:
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
            # Firewall log model only has 'text' field — use text__contains
            logs = await client.get_logs_by_ip(ip_address, safe_lines)
        else:
            # Validate log_type against allowlist to prevent path traversal
            if log_type not in _VALID_LOG_TYPES:
                return {
                    "success": False,
                    "error": f"Invalid log_type '{log_type}'. Must be one of: {', '.join(sorted(_VALID_LOG_TYPES))}",
                }
            # Non-firewall log models may have a 'message' field
            filters = [QueryFilter("text", ip_address, "contains")]
            logs = await client.get_logs(
                log_type=log_type,
                lines=safe_lines,
                filters=filters,
            )

        log_entries = logs.get("data", [])

        # Pattern analysis on raw text lines
        # Firewall log entries are raw text; we search for keywords
        if log_type == "firewall" and log_entries:
            patterns = {
                "total_entries": len(log_entries),
                "blocked_count": 0,
                "allowed_count": 0,
            }

            for entry in log_entries:
                text = entry.get("text", "").lower()
                if "block" in text or "reject" in text:
                    patterns["blocked_count"] += 1
                elif "pass" in text:
                    patterns["allowed_count"] += 1
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
