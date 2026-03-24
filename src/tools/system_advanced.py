"""Advanced system settings, REST API management, and remaining system endpoints for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..helpers import create_pagination, create_default_sort, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations
from ..guardrails import rate_limited


# ---------------------------------------------------------------------------
# System Timezone
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_system_timezone() -> Dict:
    """Get the current system timezone setting"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/system/timezone")

        return {
            "success": True,
            "timezone": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get system timezone: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_system_timezone(
    timezone_name: str,
    apply_immediately: bool = True,
) -> Dict:
    """Update the system timezone

    Args:
        timezone_name: Timezone string (e.g., 'America/New_York', 'UTC', 'Europe/London')
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict = {
            "timezone": timezone_name,
        }

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings("/system/timezone", updates, control)

        return {
            "success": True,
            "message": f"System timezone updated to '{timezone_name}'",
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update system timezone: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# System Console
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_system_console() -> Dict:
    """Get the system console settings"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/system/console")

        return {
            "success": True,
            "console": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get system console settings: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_system_console(
    primaryconsole: Optional[str] = None,
    secondaryconsole: Optional[str] = None,
    serialspeed: Optional[int] = None,
    disableconsolemenu: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update the system console settings

    Args:
        primaryconsole: Primary console type (e.g., 'video', 'serial')
        secondaryconsole: Secondary console type
        serialspeed: Serial port speed (e.g., 9600, 115200)
        disableconsolemenu: Whether to disable the console menu
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict = {}

        if primaryconsole is not None:
            updates["primaryconsole"] = primaryconsole
        if secondaryconsole is not None:
            updates["secondaryconsole"] = secondaryconsole
        if serialspeed is not None:
            updates["serialspeed"] = serialspeed
        if disableconsolemenu is not None:
            updates["disableconsolemenu"] = disableconsolemenu

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings("/system/console", updates, control)

        return {
            "success": True,
            "message": "System console settings updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update system console settings: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# WebGUI Settings
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_webgui_settings() -> Dict:
    """Get the WebGUI settings (protocol, port, certificates, etc.)"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/system/webgui/settings")

        return {
            "success": True,
            "settings": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get WebGUI settings: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_webgui_settings(
    protocol: Optional[str] = None,
    port: Optional[int] = None,
    ssl_certref: Optional[str] = None,
    max_processes: Optional[int] = None,
    noantilockout: Optional[bool] = None,
    nodnsrebindcheck: Optional[bool] = None,
    nohttpreferercheck: Optional[bool] = None,
    loginautocomplete: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update the WebGUI settings

    Args:
        protocol: WebGUI protocol ('http' or 'https')
        port: WebGUI listening port
        ssl_certref: SSL certificate reference ID
        max_processes: Maximum number of webConfigurator processes
        noantilockout: Disable anti-lockout rule
        nodnsrebindcheck: Disable DNS rebinding checks
        nohttpreferercheck: Disable HTTP referer enforcement
        loginautocomplete: Allow login autocomplete
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict = {}

        if protocol is not None:
            if protocol not in ("http", "https"):
                return {"success": False, "error": "protocol must be 'http' or 'https'"}
            updates["protocol"] = protocol
        if port is not None:
            if port < 1 or port > 65535:
                return {"success": False, "error": "port must be between 1 and 65535"}
            updates["port"] = port
        if ssl_certref is not None:
            updates["ssl-certref"] = ssl_certref
        if max_processes is not None:
            updates["max_procs"] = max_processes
        if noantilockout is not None:
            updates["noantilockout"] = noantilockout
        if nodnsrebindcheck is not None:
            updates["nodnsrebindcheck"] = nodnsrebindcheck
        if nohttpreferercheck is not None:
            updates["nohttpreferercheck"] = nohttpreferercheck
        if loginautocomplete is not None:
            updates["loginautocomplete"] = loginautocomplete

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings("/system/webgui/settings", updates, control)

        return {
            "success": True,
            "message": "WebGUI settings updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update WebGUI settings: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Email Notification Settings
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_email_notification_settings() -> Dict:
    """Get the email notification settings"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/system/notifications/email_settings")

        return {
            "success": True,
            "settings": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get email notification settings: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_email_notification_settings(
    disabled: Optional[bool] = None,
    ipaddress: Optional[str] = None,
    port: Optional[int] = None,
    timeout: Optional[int] = None,
    ssl: Optional[bool] = None,
    sslvalidate: Optional[bool] = None,
    fromaddress: Optional[str] = None,
    notifyemailaddress: Optional[str] = None,
    authentication_mechanism: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update the email notification settings

    Args:
        disabled: Whether email notifications are disabled
        ipaddress: SMTP server IP address or hostname
        port: SMTP server port
        timeout: Connection timeout in seconds
        ssl: Whether to use SSL/TLS
        sslvalidate: Whether to validate SSL certificates
        fromaddress: From email address
        notifyemailaddress: Notification recipient email address
        authentication_mechanism: Auth mechanism (e.g., 'PLAIN', 'LOGIN')
        username: SMTP authentication username
        password: SMTP authentication password
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict = {}

        if disabled is not None:
            updates["disabled"] = disabled
        if ipaddress is not None:
            updates["ipaddress"] = ipaddress
        if port is not None:
            updates["port"] = port
        if timeout is not None:
            updates["timeout"] = timeout
        if ssl is not None:
            updates["ssl"] = ssl
        if sslvalidate is not None:
            updates["sslvalidate"] = sslvalidate
        if fromaddress is not None:
            updates["fromaddress"] = fromaddress
        if notifyemailaddress is not None:
            updates["notifyemailaddress"] = notifyemailaddress
        if authentication_mechanism is not None:
            updates["authentication_mechanism"] = authentication_mechanism
        if username is not None:
            updates["username"] = username
        if password is not None:
            updates["password"] = password

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings(
            "/system/notifications/email_settings", updates, control
        )

        return {
            "success": True,
            "message": "Email notification settings updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update email notification settings: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Log Settings
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_log_settings() -> Dict:
    """Get the system log settings"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/status/logs/settings")

        return {
            "success": True,
            "settings": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get log settings: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_log_settings(
    format: Optional[str] = None,
    reverse: Optional[bool] = None,
    nentries: Optional[int] = None,
    logfilesize: Optional[int] = None,
    remoteserver: Optional[str] = None,
    remoteserver2: Optional[str] = None,
    remoteserver3: Optional[str] = None,
    sourceip: Optional[str] = None,
    ipproto: Optional[str] = None,
    logall: Optional[bool] = None,
    filter: Optional[bool] = None,
    dhcp: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update the system log settings

    Args:
        format: Log format ('rfc3164' or 'rfc5424')
        reverse: Whether to display logs in reverse order (newest first)
        nentries: Number of log entries to display per page
        logfilesize: Maximum log file size in bytes
        remoteserver: Primary remote syslog server (IP:port)
        remoteserver2: Secondary remote syslog server
        remoteserver3: Tertiary remote syslog server
        sourceip: Source IP address for syslog messages
        ipproto: IP protocol for remote syslog ('ipv4' or 'ipv6')
        logall: Log all packets (not just those matching rules)
        filter: Log packets matched by firewall rules
        dhcp: Log DHCP events
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict = {}

        if format is not None:
            updates["format"] = format
        if reverse is not None:
            updates["reverse"] = reverse
        if nentries is not None:
            updates["nentries"] = nentries
        if logfilesize is not None:
            updates["logfilesize"] = logfilesize
        if remoteserver is not None:
            updates["remoteserver"] = remoteserver
        if remoteserver2 is not None:
            updates["remoteserver2"] = remoteserver2
        if remoteserver3 is not None:
            updates["remoteserver3"] = remoteserver3
        if sourceip is not None:
            updates["sourceip"] = sourceip
        if ipproto is not None:
            updates["ipproto"] = ipproto
        if logall is not None:
            updates["logall"] = logall
        if filter is not None:
            updates["filter"] = filter
        if dhcp is not None:
            updates["dhcp"] = dhcp

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings("/status/logs/settings", updates, control)

        return {
            "success": True,
            "message": "Log settings updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update log settings: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# DHCP Relay
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_dhcp_relay_settings() -> Dict:
    """Get the DHCP relay settings"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/services/dhcp_relay")

        return {
            "success": True,
            "settings": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get DHCP relay settings: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_dhcp_relay_settings(
    enable: Optional[bool] = None,
    interface: Optional[List[str]] = None,
    server: Optional[List[str]] = None,
    agentoption: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update the DHCP relay settings

    Args:
        enable: Whether to enable the DHCP relay
        interface: List of interfaces to relay on
        server: List of DHCP server IP addresses to relay to
        agentoption: Whether to append circuit ID and agent ID
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict = {}

        if enable is not None:
            updates["enable"] = enable
        if interface is not None:
            updates["interface"] = interface
        if server is not None:
            updates["server"] = server
        if agentoption is not None:
            updates["agentoption"] = agentoption

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings("/services/dhcp_relay", updates, control)

        return {
            "success": True,
            "message": "DHCP relay settings updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update DHCP relay settings: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Firewall Advanced Settings
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_firewall_advanced_settings(
    optimization: Optional[str] = None,
    maximumstates: Optional[int] = None,
    maximumtableentries: Optional[int] = None,
    maximumfrags: Optional[int] = None,
    bypassstaticroutes: Optional[bool] = None,
    bogonsinterval: Optional[str] = None,
    disablefilter: Optional[bool] = None,
    disablescrub: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update firewall advanced settings

    Args:
        optimization: Firewall optimization mode ('normal', 'high-latency', 'aggressive', 'conservative')
        maximumstates: Maximum number of firewall state table entries
        maximumtableentries: Maximum number of table entries for aliases
        maximumfrags: Maximum number of fragment entries
        bypassstaticroutes: Bypass firewall rules for traffic on same interface
        bogonsinterval: Bogon network update interval ('monthly', 'never')
        disablefilter: Disable all packet filtering
        disablescrub: Disable packet scrubbing
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict = {}

        if optimization is not None:
            valid_opts = ("normal", "high-latency", "aggressive", "conservative")
            if optimization not in valid_opts:
                return {
                    "success": False,
                    "error": f"optimization must be one of: {', '.join(valid_opts)}",
                }
            updates["optimization"] = optimization
        if maximumstates is not None:
            updates["maximumstates"] = maximumstates
        if maximumtableentries is not None:
            updates["maximumtableentries"] = maximumtableentries
        if maximumfrags is not None:
            updates["maximumfrags"] = maximumfrags
        if bypassstaticroutes is not None:
            updates["bypassstaticroutes"] = bypassstaticroutes
        if bogonsinterval is not None:
            updates["bogonsinterval"] = bogonsinterval
        if disablefilter is not None:
            updates["disablefilter"] = disablefilter
        if disablescrub is not None:
            updates["disablescrub"] = disablescrub

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings(
            "/firewall/advanced_settings", updates, control
        )

        return {
            "success": True,
            "message": "Firewall advanced settings updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update firewall advanced settings: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Firewall State Size
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_firewall_state_size(
    maximumstates: Optional[int] = None,
    defaultstatesize: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update the firewall state table size

    Args:
        maximumstates: Maximum number of state table entries (0 for default)
        defaultstatesize: Whether to use the default state size
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict = {}

        if maximumstates is not None:
            updates["maximumstates"] = maximumstates
        if defaultstatesize is not None:
            updates["defaultstatesize"] = defaultstatesize

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings("/firewall/states/size", updates, control)

        return {
            "success": True,
            "message": "Firewall state size updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update firewall state size: {e}")
        return {"success": False, "error": str(e)}
