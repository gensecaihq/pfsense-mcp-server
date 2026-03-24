"""Standalone helper functions for common query patterns and safety guards."""

import ipaddress
import logging
import re
from typing import Dict, List, Optional, Union

from .models import PaginationOptions, QueryFilter, SortOptions

logger = logging.getLogger(__name__)


# Safety constants
MAX_LOG_LINES = 50

# Allowlist of valid pfSense REST API v2 log endpoints
# Maps to /api/v2/status/logs/<type>
VALID_LOG_TYPES = frozenset({
    "firewall", "system", "dhcp", "openvpn", "auth",
})


def safe_data_dict(result: Dict) -> Dict:
    """Safely extract the 'data' dict from an API response.

    Returns the data dict if present and is a dict, otherwise an empty dict.
    Guards against data=null, data="string", or missing data key.
    """
    data = result.get("data") if isinstance(result, dict) else None
    return data if isinstance(data, dict) else {}


def safe_data_list(result: Dict) -> List:
    """Safely extract the 'data' list from an API response.

    Returns the data list if present and is a list, otherwise an empty list.
    """
    data = result.get("data") if isinstance(result, dict) else None
    return data if isinstance(data, list) else []


MAX_DESCRIPTION_LENGTH = 1024


def sanitize_description(descr: str) -> str:
    """Sanitize and cap a description field to prevent issues with pfSense config.

    Strips control characters, truncates to MAX_DESCRIPTION_LENGTH.
    """
    # Remove control characters (keep newlines and tabs)
    cleaned = "".join(c for c in descr if c == "\n" or c == "\t" or (ord(c) >= 32))
    if len(cleaned) > MAX_DESCRIPTION_LENGTH:
        cleaned = cleaned[:MAX_DESCRIPTION_LENGTH]
    return cleaned


def create_ip_filter(ip_address: str, operator: str = "exact") -> QueryFilter:
    """Create filter for IP address fields"""
    return QueryFilter("ip", ip_address, operator)


def create_port_filter(port: Union[int, str], field: str = "destination_port", operator: str = "exact") -> QueryFilter:
    """Create filter for port fields"""
    return QueryFilter(field, str(port), operator)


def create_interface_filter(interface: str) -> QueryFilter:
    """Create filter for interface fields (uses contains since interface is an array)"""
    return QueryFilter("interface", interface, "contains")


def create_date_range_filters(
    field: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[QueryFilter]:
    """Create date range filters"""
    filters = []
    if start_date:
        filters.append(QueryFilter(field, start_date, "gte"))
    if end_date:
        filters.append(QueryFilter(field, end_date, "lte"))
    return filters


MAX_PAGE_SIZE = 200

# Cap max offset to prevent pfSense PHP memory exhaustion.
# 10,000 objects × 200 per page = page 50 max is generous for any pfSense install.
MAX_PAGE = 500
MAX_OFFSET = MAX_PAGE * MAX_PAGE_SIZE  # 100,000


def create_pagination(page: int, page_size: int = 50) -> tuple:
    """Create pagination options (capped to avoid pfSense PHP memory exhaustion).

    Returns:
        (PaginationOptions, normalized_page, normalized_page_size)
    """
    if page < 1:
        page = 1
    if page > MAX_PAGE:
        page = MAX_PAGE
    if page_size < 1:
        page_size = 50
    safe_size = min(page_size, MAX_PAGE_SIZE)
    offset = min((page - 1) * safe_size, MAX_OFFSET)
    return PaginationOptions(limit=safe_size, offset=offset), page, safe_size


def create_default_sort(field: str, descending: bool = False) -> SortOptions:
    """Create default sort options"""
    return SortOptions(
        sort_by=field,
        sort_order="SORT_DESC" if descending else "SORT_ASC"
    )


# Valid port value: single port (443), range (1024-65535), or alias name (alphanumeric/underscore)
_PORT_RE = re.compile(r"^(\d{1,5}(-\d{1,5})?|[A-Za-z_]\w*)$")

_MAX_PORT = 65535


def validate_port_value(value: str, field_name: str = "port") -> Optional[str]:
    """Return an error message if the port value looks invalid, else None."""
    stripped = value.strip() if value else ""
    if not stripped:
        return None

    m = _PORT_RE.match(stripped)
    if not m:
        return (
            f"Invalid {field_name} '{value}'. "
            "Use a single port (443), a range (1024-65535), or an alias name. "
            "Multiple ports require a port alias — create one first with create_alias."
        )

    # If it matched the numeric pattern, validate port bounds and range ordering
    if stripped[0].isdigit():
        parts = stripped.split("-")
        for p in parts:
            if int(p) < 1 or int(p) > _MAX_PORT:
                return (
                    f"Invalid {field_name} '{value}': port numbers must be 1-{_MAX_PORT}."
                )
        if len(parts) == 2 and int(parts[0]) > int(parts[1]):
            return (
                f"Invalid {field_name} '{value}': range start must be <= range end."
            )

    return None


def safe_log_lines(lines: int) -> int:
    """Cap log lines to prevent pfSense PHP memory exhaustion."""
    return max(1, min(lines, MAX_LOG_LINES))


def validate_log_type(log_type: str) -> str:
    """Validate log type against allowlist to prevent path traversal."""
    log_type = log_type.lower().strip()
    if log_type not in VALID_LOG_TYPES:
        raise ValueError(
            f"Invalid log type '{log_type}'. "
            f"Allowed: {', '.join(sorted(VALID_LOG_TYPES))}"
        )
    return log_type


def validate_ip_address(ip: str) -> str:
    """Validate an IP address or network. Returns normalized string."""
    ip = ip.strip()
    if ip.lower() == "any":
        return "any"
    try:
        ipaddress.ip_network(ip, strict=False)
    except ValueError as e:
        raise ValueError(f"Invalid IP address or network '{ip}': {e}") from e
    return ip


def ensure_interface_list(interface: Union[str, list]) -> list:
    """Ensure interface value is a list as required by pfSense API v2."""
    if isinstance(interface, str):
        return [interface]
    return interface


def normalize_protocol(protocol: Optional[str]) -> Optional[str]:
    """Normalize protocol value: 'any' becomes None per pfSense API v2."""
    if protocol is None:
        return None
    if protocol.lower() == "any":
        return None
    return protocol.lower()


# Alias name: 1-31 chars, starts with letter or underscore, alphanumeric/underscores only
_ALIAS_NAME_RE = re.compile(r"^[A-Za-z_]\w{0,30}$")

VALID_ALIAS_TYPES = frozenset({"host", "network", "port", "url"})

VALID_PROTOCOLS = frozenset({"tcp", "udp", "icmp", "tcp/udp", "any"})

_MAC_COLON_RE = re.compile(r"^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$")
_MAC_HYPHEN_RE = re.compile(r"^([0-9a-fA-F]{2}-){5}[0-9a-fA-F]{2}$")
_MAC_BARE_RE = re.compile(r"^[0-9a-fA-F]{12}$")

MAX_BULK_IPS = 100


def validate_alias_name(name: str) -> Optional[str]:
    """Return an error message if the alias name is invalid, else None."""
    if not _ALIAS_NAME_RE.match(name):
        return (
            f"Invalid alias name '{name}'. Must be 1-31 characters, "
            "start with a letter or underscore, and contain only "
            "alphanumeric characters and underscores."
        )
    return None


def normalize_mac_address(mac: str) -> str:
    """Normalize a MAC address to colon-separated lowercase format.

    Accepts colon-separated (AA:BB:CC:DD:EE:FF),
    hyphen-separated (AA-BB-CC-DD-EE-FF),
    and bare (AABBCCDDEEFF) formats.

    Returns:
        Normalized MAC in XX:XX:XX:XX:XX:XX format (lowercase).

    Raises:
        ValueError: If the MAC address is not valid in any supported format.
    """
    stripped = mac.strip()
    if _MAC_COLON_RE.match(stripped):
        return stripped.lower()
    if _MAC_HYPHEN_RE.match(stripped):
        return stripped.replace("-", ":").lower()
    if _MAC_BARE_RE.match(stripped):
        h = stripped.lower()
        return ":".join(h[i:i+2] for i in range(0, 12, 2))
    raise ValueError(
        f"Invalid MAC address '{mac}'. Accepted formats: "
        "XX:XX:XX:XX:XX:XX, XX-XX-XX-XX-XX-XX, or XXXXXXXXXXXX"
    )


def validate_mac_address(mac: str) -> Optional[str]:
    """Return an error message if the MAC address is invalid, else None."""
    try:
        normalize_mac_address(mac)
        return None
    except ValueError as e:
        return str(e)


def validate_protocol(protocol: str) -> Optional[str]:
    """Return an error message if the protocol is invalid, else None."""
    if protocol.lower() not in VALID_PROTOCOLS:
        return (
            f"Invalid protocol '{protocol}'. "
            f"Must be one of: {', '.join(sorted(VALID_PROTOCOLS))}"
        )
    return None


def validate_alias_addresses(alias_type: str, addresses: List[str]) -> Optional[str]:
    """Validate that addresses are appropriate for the alias type.

    Returns an error message if validation fails, else None.
    """
    if not addresses:
        return "Address list cannot be empty."

    for addr in addresses:
        addr = addr.strip()
        if not addr:
            return "Address list contains an empty entry."

        if alias_type == "host":
            # Must be a valid IP address (not a network with prefix) or alias name
            try:
                parsed = ipaddress.ip_address(addr)
                continue  # valid IP
            except ValueError:
                pass
            # Could be an alias name (alphanumeric/underscore)
            if _ALIAS_NAME_RE.match(addr):
                continue
            return (
                f"Invalid host alias entry '{addr}'. "
                "Must be an IP address (e.g., 10.0.0.1) or an existing alias name."
            )

        elif alias_type == "network":
            # Must be a valid CIDR network or alias name
            try:
                ipaddress.ip_network(addr, strict=False)
                continue
            except ValueError:
                pass
            if _ALIAS_NAME_RE.match(addr):
                continue
            return (
                f"Invalid network alias entry '{addr}'. "
                "Must be a CIDR network (e.g., 10.0.0.0/24) or an existing alias name."
            )

        elif alias_type == "port":
            err = validate_port_value(addr, "port alias entry")
            if err:
                return err

        elif alias_type == "url":
            if not addr.startswith(("http://", "https://")):
                return (
                    f"Invalid URL alias entry '{addr}'. "
                    "Must start with http:// or https://"
                )

    return None


# --------------------------------------------------------------------------- #
# pfSense filterlog parser
# --------------------------------------------------------------------------- #
# pfSense filterlog format (CSV after the syslog prefix):
#   rule_number, sub_rule, anchor, tracker, interface, reason, action,
#   direction, ip_version, ...
# For IPv4 (ip_version=4):
#   ..., tos, ecn, ttl, id, offset, flags, proto_id, protocol, length,
#   src_ip, dst_ip, [src_port, dst_port if TCP/UDP]
# For IPv6 (ip_version=6):
#   ..., class, flow_label, hop_limit, protocol, proto_id, length,
#   src_ip, dst_ip, [src_port, dst_port if TCP/UDP]

def parse_filterlog_entry(text: str) -> Optional[Dict[str, str]]:
    """Parse a pfSense filterlog syslog line into structured fields.

    Returns a dict with keys: action, interface, direction, ip_version,
    protocol, src_ip, dst_ip, src_port, dst_port (if applicable).
    Returns None if the line cannot be parsed.
    """
    if not text:
        return None

    # Strip the syslog prefix (everything up to and including "filterlog[NNNN]: ")
    marker = "filterlog["
    idx = text.find(marker)
    if idx == -1:
        return None
    colon_idx = text.find("]: ", idx)
    if colon_idx == -1:
        return None
    csv_part = text[colon_idx + 3:]

    fields = csv_part.split(",")
    if len(fields) < 7:
        return None

    result: Dict[str, str] = {
        "tracker": fields[3] if len(fields) > 3 else "",
        "interface": fields[4] if len(fields) > 4 else "",
        "reason": fields[5] if len(fields) > 5 else "",
        "action": fields[6] if len(fields) > 6 else "",
        "direction": fields[7] if len(fields) > 7 else "",
        "ip_version": fields[8] if len(fields) > 8 else "",
    }

    ip_ver = result["ip_version"]

    if ip_ver == "4" and len(fields) >= 20:
        result["protocol"] = fields[16] if len(fields) > 16 else ""
        # Validate extracted IPs to guard against format changes
        raw_src = fields[18] if len(fields) > 18 else ""
        raw_dst = fields[19] if len(fields) > 19 else ""
        try:
            ipaddress.ip_address(raw_src)
            result["src_ip"] = raw_src
        except ValueError:
            result["src_ip"] = ""
        try:
            ipaddress.ip_address(raw_dst)
            result["dst_ip"] = raw_dst
        except ValueError:
            result["dst_ip"] = ""
        # TCP/UDP have src_port and dst_port after dst_ip
        if len(fields) >= 22:
            result["src_port"] = fields[20]
            result["dst_port"] = fields[21]

    elif ip_ver == "6" and len(fields) >= 17:
        result["protocol"] = fields[12] if len(fields) > 12 else ""
        # IPv6 addresses are validated more loosely (contain colons)
        raw_src = fields[15] if len(fields) > 15 else ""
        raw_dst = fields[16] if len(fields) > 16 else ""
        try:
            ipaddress.ip_address(raw_src)
            result["src_ip"] = raw_src
        except ValueError:
            result["src_ip"] = ""
        try:
            ipaddress.ip_address(raw_dst)
            result["dst_ip"] = raw_dst
        except ValueError:
            result["dst_ip"] = ""
        # TCP/UDP have src_port and dst_port after dst_ip
        if len(fields) >= 19:
            result["src_port"] = fields[17]
            result["dst_port"] = fields[18]

    else:
        # Fallback: try to extract IPs via regex but validate them
        _ipv4_re = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
        candidates = _ipv4_re.findall(csv_part)
        valid_ips = []
        for c in candidates:
            try:
                ipaddress.ip_address(c)
                valid_ips.append(c)
            except ValueError:
                continue
        if valid_ips:
            result["src_ip"] = valid_ips[0]
            if len(valid_ips) > 1:
                result["dst_ip"] = valid_ips[1]

    return result
