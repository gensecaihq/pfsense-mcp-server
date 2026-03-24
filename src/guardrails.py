"""Defense-in-depth guardrail system for destructive pfSense MCP operations.

Implements multiple layers of protection following security best practices:

1. Action Classification — categorizes every operation by risk level
2. Approval Gate — mandatory confirmation with full command visualization
3. Audit Logging — immutable log of all destructive actions taken
4. Rate Limiting — prevents runaway automation from mass-modifying config
5. Dry-Run Mode — preview what an operation would do without executing
6. Rollback Tracking — records state before destructive changes
7. Command Allowlisting — only explicitly permitted operations execute
8. Input Sanitization — defense against injection via tool parameters
"""

import hashlib
import json
import logging
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Action Classification
# ---------------------------------------------------------------------------

class RiskLevel(str, Enum):
    """Risk classification for MCP tool operations."""
    READ = "read"              # No state change (search, get, list)
    LOW = "low"                # Reversible state change (enable/disable, update settings)
    MEDIUM = "medium"          # Significant change (create rule, update config)
    HIGH = "high"              # Destructive/irreversible (delete, bulk operations)
    CRITICAL = "critical"      # System-level destructive (reboot, halt, bulk delete, wipe)


# Map of tool name patterns to risk levels
_RISK_CLASSIFICATION = {
    # CRITICAL — system-level destructive
    "halt_system": RiskLevel.CRITICAL,
    "reboot_system": RiskLevel.CRITICAL,
    "bulk_block_ips": RiskLevel.CRITICAL,

    # HIGH — destructive/irreversible
    "delete_": RiskLevel.HIGH,
    "disconnect_": RiskLevel.HIGH,

    # MEDIUM — significant changes
    "create_": RiskLevel.MEDIUM,
    "move_": RiskLevel.MEDIUM,
    "manage_": RiskLevel.MEDIUM,
    "send_wake_on_lan": RiskLevel.MEDIUM,
    "issue_": RiskLevel.MEDIUM,
    "renew_": RiskLevel.MEDIUM,
    "register_": RiskLevel.MEDIUM,
    "generate_": RiskLevel.MEDIUM,
    "export_": RiskLevel.MEDIUM,

    # LOW — reversible settings changes
    "update_": RiskLevel.LOW,
    "apply_": RiskLevel.LOW,
    "enable_": RiskLevel.LOW,
    "disable_": RiskLevel.LOW,
    "control_service": RiskLevel.LOW,

    # READ — no state change
    "search_": RiskLevel.READ,
    "get_": RiskLevel.READ,
    "find_": RiskLevel.READ,
    "analyze_": RiskLevel.READ,
    "follow_": RiskLevel.READ,
    "test_": RiskLevel.READ,
    "system_status": RiskLevel.READ,
    "refresh_": RiskLevel.READ,
    "run_ping": RiskLevel.READ,
}


def classify_risk(tool_name: str) -> RiskLevel:
    """Classify the risk level of a tool by name.

    Checks exact matches first, then prefix matches.
    Defaults to MEDIUM for unknown tools (fail-safe).
    """
    # Exact match first
    if tool_name in _RISK_CLASSIFICATION:
        return _RISK_CLASSIFICATION[tool_name]
    # Prefix match
    for pattern, level in _RISK_CLASSIFICATION.items():
        if tool_name.startswith(pattern):
            return level
    # Unknown tools default to MEDIUM (fail-safe, not fail-open)
    return RiskLevel.MEDIUM


# ---------------------------------------------------------------------------
# 2. Approval Gate — Full Command Visualization
# ---------------------------------------------------------------------------

@dataclass
class ApprovalRequest:
    """Represents a pending destructive action requiring approval."""
    tool_name: str
    risk_level: RiskLevel
    parameters: Dict[str, Any]
    description: str
    impact_summary: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    request_id: str = ""

    def __post_init__(self):
        if not self.request_id:
            # Deterministic ID from tool + params + time for idempotency
            content = f"{self.tool_name}:{json.dumps(self.parameters, sort_keys=True)}:{self.timestamp}"
            self.request_id = hashlib.sha256(content.encode()).hexdigest()[:16]


def build_approval_request(
    tool_name: str,
    parameters: Dict[str, Any],
    description: str,
) -> Dict:
    """Build a human-readable approval request for a destructive operation.

    Returns a dict that the MCP client should display to the user for
    explicit confirmation before proceeding.
    """
    risk = classify_risk(tool_name)
    impact = _build_impact_summary(tool_name, parameters)

    request = ApprovalRequest(
        tool_name=tool_name,
        risk_level=risk,
        parameters=_redact_sensitive(parameters),
        description=description,
        impact_summary=impact,
    )

    return {
        "success": False,
        "approval_required": True,
        "error": f"This is a {risk.value}-risk operation. Set confirm=True to proceed.",
        "request_id": request.request_id,
        "risk_level": risk.value,
        "tool": tool_name,
        "impact": impact,
        "parameters_visible": request.parameters,
        "reversible": risk != RiskLevel.CRITICAL,
        "how_to_proceed": f"Call {tool_name}(..., confirm=True) to execute.",
        "how_to_preview": f"Call {tool_name}(..., dry_run=True) to preview without executing.",
        "how_to_verify": "Use find_object_by_field() or search tools to verify the target object before confirming." if "delete" in tool_name else None,
        "timestamp": request.timestamp,
    }


def _extract_object_id(params: Dict) -> str:
    """Extract the object ID from parameters, trying common field names."""
    for key in ("rule_id", "alias_id", "id", "mapping_id", "port_forward_id",
                "tunnel_id", "peer_id", "override_id", "access_list_id",
                "certificate_id", "ca_id", "crl_id", "user_id", "client_id",
                "gateway_id", "group_id", "route_id", "schedule_id", "tunable_id",
                "shaper_id", "queue_id", "limiter_id", "vlan_id", "interface_id",
                "vip_id", "state_id", "revision_id", "backend_id", "frontend_id",
                "zone_id", "record_id"):
        val = params.get(key)
        if val is not None:
            return str(val)
    return "unknown"


def _build_impact_summary(tool_name: str, params: Dict) -> str:
    """Generate a detailed, human-readable impact summary for informed decision-making."""
    if tool_name == "halt_system":
        return (
            "WILL SHUT DOWN the pfSense appliance. All network traffic will stop immediately. "
            "Physical access or out-of-band management (IPMI/iLO) required to restart. "
            "This action is IRREVERSIBLE remotely."
        )
    if tool_name == "reboot_system":
        return (
            "WILL REBOOT the pfSense appliance. Network traffic will be interrupted for 1-5 minutes. "
            "All active VPN tunnels, NAT sessions, and firewall states will be dropped. "
            "The appliance will come back online automatically."
        )
    if tool_name == "bulk_block_ips":
        ips = params.get("ip_addresses", [])
        count = len(ips)
        iface = params.get("interface", "wan")
        ip_preview = ", ".join(ips[:5])
        if count > 5:
            ip_preview += f", ... and {count - 5} more"
        return (
            f"Will create {count} BLOCK rules on interface '{iface}' for: {ip_preview}. "
            f"These rules will drop all traffic from the listed IPs. "
            f"Rules are created with apply=True and will take effect immediately."
        )
    if tool_name.startswith("delete_"):
        obj_type = tool_name.replace("delete_", "").replace("_", " ")
        obj_id = _extract_object_id(params)
        apply = params.get("apply_immediately", True)
        verify = params.get("verify_descr")
        lines = [
            f"Will PERMANENTLY DELETE {obj_type} with ID {obj_id}.",
            f"Apply immediately: {'yes' if apply else 'no (pending until manual apply)'}.",
            "After deletion, all subsequent object IDs will shift down by 1.",
            "This action CANNOT be undone — the object and its configuration will be lost.",
        ]
        if verify:
            lines.append(f"Stale-ID guard active: will verify descr='{verify}' before deleting.")
        return " ".join(lines)
    if tool_name == "disconnect_openvpn_client":
        return (
            "Will forcibly disconnect an active OpenVPN client connection. "
            "The client may automatically reconnect depending on its configuration."
        )
    if tool_name.startswith("create_"):
        obj_type = tool_name.replace("create_", "").replace("_", " ")
        apply = params.get("apply_immediately", True)
        return (
            f"Will create a new {obj_type} on the live pfSense appliance. "
            f"Apply immediately: {'yes — changes take effect now' if apply else 'no — requires manual apply'}."
        )
    return f"Will execute {tool_name.replace('_', ' ')} on the live pfSense appliance."


def _redact_sensitive(params: Dict) -> Dict:
    """Redact sensitive values from parameters for display.

    Passwords, keys, and secrets are replaced with '***REDACTED***'.
    """
    sensitive_keys = {"password", "pre_shared_key", "presharedkey", "privatekey",
                      "secret", "passphrase", "api_key", "prv", "key",
                      "pwd", "passwd", "token", "jwt_token", "bearer_token",
                      "cert", "certificate"}
    redacted = {}
    for k, v in params.items():
        if k.lower() in sensitive_keys:
            redacted[k] = "***REDACTED***"
        elif isinstance(v, dict):
            redacted[k] = _redact_sensitive(v)
        elif isinstance(v, list):
            redacted[k] = [
                _redact_sensitive(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            redacted[k] = v
    return redacted


# ---------------------------------------------------------------------------
# 3. Audit Logging — Immutable Record of All Destructive Actions
# ---------------------------------------------------------------------------

# Audit log file path (configurable via env var)
_AUDIT_LOG_PATH = os.getenv("MCP_AUDIT_LOG", "")


def audit_log(
    tool_name: str,
    risk_level: RiskLevel,
    parameters: Dict,
    result: str,
    user_confirmed: bool = False,
):
    """Write an immutable audit log entry for a destructive action.

    Format: JSON lines (one JSON object per line) for easy parsing.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "risk_level": risk_level.value,
        "parameters": _redact_sensitive(parameters),
        "result": result,
        "confirmed": user_confirmed,
    }

    # Always log to Python logger
    logger.info("AUDIT: %s [%s] confirmed=%s result=%s",
                tool_name, risk_level.value, user_confirmed, result)

    # Optionally write to dedicated audit file
    if _AUDIT_LOG_PATH:
        try:
            with open(_AUDIT_LOG_PATH, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError as e:
            logger.warning("Failed to write audit log to %s: %s", _AUDIT_LOG_PATH, e)


# ---------------------------------------------------------------------------
# 4. Rate Limiting — Prevent Runaway Automation
# ---------------------------------------------------------------------------

@dataclass
class RateLimiter:
    """Sliding window rate limiter for destructive operations.

    Prevents rapid-fire destructive actions that could indicate
    a runaway LLM loop or compromised client.
    """
    # Max operations per window (configurable via env)
    max_ops: int = 10
    window_seconds: int = 60
    _timestamps: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))

    def check(self, category: str) -> Optional[str]:
        """Check if the rate limit is exceeded.

        Returns None if OK, or an error message if rate-limited.
        """
        now = time.time()
        cutoff = now - self.window_seconds
        # Clean old entries
        self._timestamps[category] = [t for t in self._timestamps[category] if t > cutoff]
        if len(self._timestamps[category]) >= self.max_ops:
            return (
                f"Rate limit exceeded: {self.max_ops} {category} operations "
                f"per {self.window_seconds}s. Wait before retrying."
            )
        self._timestamps[category].append(now)
        return None


# Global rate limiters
_delete_limiter = RateLimiter(
    max_ops=int(os.getenv("MCP_RATE_LIMIT_DELETE", "10")),
    window_seconds=60,
)
_create_limiter = RateLimiter(
    max_ops=int(os.getenv("MCP_RATE_LIMIT_CREATE", "20")),
    window_seconds=60,
)
_critical_limiter = RateLimiter(
    max_ops=int(os.getenv("MCP_RATE_LIMIT_CRITICAL", "2")),
    window_seconds=300,  # 5-minute window for critical ops
)


def reset_rate_limiters():
    """Reset all rate limiters (for testing)."""
    _delete_limiter._timestamps.clear()
    _create_limiter._timestamps.clear()
    _critical_limiter._timestamps.clear()


def check_rate_limit(tool_name: str) -> Optional[str]:
    """Check rate limits based on operation type.

    Returns None if OK, or an error message if rate-limited.
    """
    risk = classify_risk(tool_name)
    if risk == RiskLevel.CRITICAL:
        return _critical_limiter.check("critical")
    if risk == RiskLevel.HIGH:
        return _delete_limiter.check("delete")
    if risk == RiskLevel.MEDIUM:
        return _create_limiter.check("create")
    return None


# ---------------------------------------------------------------------------
# 5. Dry-Run Mode
# ---------------------------------------------------------------------------

def build_dry_run_response(
    tool_name: str,
    parameters: Dict,
    description: str,
) -> Dict:
    """Build a dry-run response showing what would happen without executing.

    Useful for previewing destructive operations before committing.
    """
    risk = classify_risk(tool_name)
    impact = _build_impact_summary(tool_name, parameters)

    return {
        "success": True,
        "dry_run": True,
        "tool": tool_name,
        "risk_level": risk.value,
        "description": description,
        "impact": impact,
        "parameters": _redact_sensitive(parameters),
        "message": "DRY RUN — no changes were made. Set dry_run=False and confirm=True to execute.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# 6. Rollback Tracking
# ---------------------------------------------------------------------------

@dataclass
class RollbackEntry:
    """Records state before a destructive operation for potential rollback."""
    tool_name: str
    object_type: str
    object_id: Any
    previous_state: Optional[Dict]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# In-memory rollback buffer (last N operations)
_MAX_ROLLBACK_ENTRIES = int(os.getenv("MCP_ROLLBACK_BUFFER", "50"))
_rollback_buffer: List[RollbackEntry] = []


def record_rollback(
    tool_name: str,
    object_type: str,
    object_id: Any,
    previous_state: Optional[Dict],
):
    """Record state before a destructive operation for potential rollback."""
    entry = RollbackEntry(
        tool_name=tool_name,
        object_type=object_type,
        object_id=object_id,
        previous_state=previous_state,
    )
    _rollback_buffer.append(entry)
    # Trim buffer
    while len(_rollback_buffer) > _MAX_ROLLBACK_ENTRIES:
        _rollback_buffer.pop(0)
    logger.debug("Rollback recorded: %s %s id=%s", tool_name, object_type, object_id)


def get_rollback_history(limit: int = 10) -> List[Dict]:
    """Get recent rollback entries for review."""
    entries = _rollback_buffer[-limit:]
    return [
        {
            "tool": e.tool_name,
            "object_type": e.object_type,
            "object_id": e.object_id,
            "has_previous_state": e.previous_state is not None,
            "timestamp": e.timestamp,
        }
        for e in reversed(entries)
    ]


# ---------------------------------------------------------------------------
# 7. Command Allowlisting
# ---------------------------------------------------------------------------

# Allowlist of permitted destructive operations.
# If MCP_ALLOWED_TOOLS env var is set (comma-separated), only those tools
# can execute destructive actions. If not set, all tools are allowed.
_ALLOWED_TOOLS_STR = os.getenv("MCP_ALLOWED_TOOLS", "")
ALLOWED_TOOLS: Optional[frozenset] = (
    frozenset(t.strip() for t in _ALLOWED_TOOLS_STR.split(",") if t.strip())
    if _ALLOWED_TOOLS_STR.strip()
    else None  # None means all tools allowed
)


def is_tool_allowed(tool_name: str) -> bool:
    """Check if a tool is in the allowlist.

    If no allowlist is configured (ALLOWED_TOOLS is None), all tools are allowed.
    Read-only tools are always allowed regardless of allowlist.
    """
    if classify_risk(tool_name) == RiskLevel.READ:
        return True
    if ALLOWED_TOOLS is None:
        return True
    return tool_name in ALLOWED_TOOLS


# ---------------------------------------------------------------------------
# 8. Input Sanitization
# ---------------------------------------------------------------------------

# Patterns that should never appear in user-supplied string parameters
_INJECTION_PATTERNS = [
    re.compile(r"\.\./"),                    # Directory traversal
    re.compile(r";\s*\w"),                   # Command chaining
    re.compile(r"\|\s*\w"),                  # Pipe injection
    re.compile(r"`[^`]+`"),                  # Backtick execution
    re.compile(r"\$\("),                     # Command substitution
    re.compile(r"\$\{"),                     # Variable expansion
    re.compile(r"<script", re.IGNORECASE),   # XSS
]


def sanitize_input(value: str, field_name: str = "input") -> Optional[str]:
    """Check a string input for injection patterns.

    Returns an error message if suspicious content found, None if clean.
    """
    if not isinstance(value, str):
        return None
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(value):
            return (
                f"Potentially unsafe content detected in '{field_name}'. "
                f"Input contains a pattern that could indicate injection. "
                f"Review the value and retry."
            )
    return None


def sanitize_parameters(params: Dict[str, Any]) -> Optional[str]:
    """Scan all string parameters for injection patterns, recursively.

    Returns the first error found, or None if all clean.
    """
    for key, value in params.items():
        if isinstance(value, str):
            err = sanitize_input(value, key)
            if err:
                return err
        elif isinstance(value, dict):
            err = sanitize_parameters(value)
            if err:
                return err
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, str):
                    err = sanitize_input(item, f"{key}[{i}]")
                    if err:
                        return err
                elif isinstance(item, dict):
                    err = sanitize_parameters(item)
                    if err:
                        return err
    return None


# ---------------------------------------------------------------------------
# Unified Guardrail Check — Call This From Every Tool
# ---------------------------------------------------------------------------

def check_guardrails(
    tool_name: str,
    parameters: Dict[str, Any],
    confirm: bool = False,
    dry_run: bool = False,
) -> Optional[Dict]:
    """Run all guardrail checks for a tool invocation.

    Returns None if all checks pass and the operation should proceed.
    Returns a response dict if the operation should be blocked or is a dry-run.

    This is the single entry point for all safety checks — every tool
    with risk >= MEDIUM should call this before executing.
    """
    risk = classify_risk(tool_name)

    # Read-only tools skip all guardrails
    if risk == RiskLevel.READ:
        return None

    # 1. Allowlist check
    if not is_tool_allowed(tool_name):
        return {
            "success": False,
            "error": f"Tool '{tool_name}' is not in the allowed tools list (MCP_ALLOWED_TOOLS).",
            "risk_level": risk.value,
        }

    # 2. Input sanitization
    injection_err = sanitize_parameters(parameters)
    if injection_err:
        return {
            "success": False,
            "error": injection_err,
            "risk_level": risk.value,
        }

    # 3. Rate limiting
    rate_err = check_rate_limit(tool_name)
    if rate_err:
        return {
            "success": False,
            "error": rate_err,
            "risk_level": risk.value,
        }

    # 4. Dry-run mode
    if dry_run:
        return build_dry_run_response(
            tool_name, parameters,
            description=_build_impact_summary(tool_name, parameters),
        )

    # 5. Confirmation gate for HIGH and CRITICAL risk
    if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL) and not confirm:
        return build_approval_request(
            tool_name, parameters,
            description=_build_impact_summary(tool_name, parameters),
        )

    # 6. Audit log (will be called, operation proceeding)
    audit_log(tool_name, risk, parameters, result="proceeding", user_confirmed=confirm)

    # All checks passed
    return None


# ---------------------------------------------------------------------------
# Guarded Tool Wrapper — Automatically applies guardrails to any tool
# ---------------------------------------------------------------------------

import functools
import inspect

from .models import PaginationOptions


def rate_limited(fn):
    """Lightweight decorator for MEDIUM-risk tools (create/update).

    Applies rate limiting, input sanitization, allowlist check, and audit logging
    WITHOUT requiring confirm or dry_run parameters. Use this for create/update
    tools that should be throttled but don't need explicit confirmation.

    Usage:
        @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False))
        @rate_limited
        async def create_something(name: str, ...):
            ...
    """
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        tool_name = fn.__name__
        risk = classify_risk(tool_name)

        if risk != RiskLevel.READ:
            # Build parameter dict for inspection
            params = {}
            sig = inspect.signature(fn)
            for name, param in sig.parameters.items():
                if name in kwargs:
                    params[name] = kwargs[name]
                elif args and list(sig.parameters.keys()).index(name) < len(args):
                    params[name] = args[list(sig.parameters.keys()).index(name)]

            # Allowlist check
            if not is_tool_allowed(tool_name):
                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' is not in the allowed tools list (MCP_ALLOWED_TOOLS).",
                }

            # Input sanitization
            injection_err = sanitize_parameters(params)
            if injection_err:
                return {"success": False, "error": injection_err}

            # Rate limiting
            rate_err = check_rate_limit(tool_name)
            if rate_err:
                return {"success": False, "error": rate_err}

            # Audit log
            audit_log(tool_name, risk, params, result="proceeding", user_confirmed=False)

        result = await fn(*args, **kwargs)

        # Post-execution audit
        if risk != RiskLevel.READ:
            success = result.get("success", False) if isinstance(result, dict) else True
            audit_log(tool_name, risk, params, result="success" if success else "failed", user_confirmed=False)

        return result

    return wrapper


def guarded(fn):
    """Decorator that applies the full guardrail system to a tool function.

    Extracts `confirm` and `dry_run` from the function's kwargs, runs
    check_guardrails() with all 8 layers, and only calls the wrapped
    function if all checks pass.

    Usage:
        @mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
        @guarded
        async def delete_something(id: int, confirm: bool = False, dry_run: bool = False):
            # This code only runs if guardrails pass
            ...

    The decorator:
    1. Extracts all non-confirm/dry_run params as the parameter dict
    2. Calls check_guardrails(tool_name, params, confirm, dry_run)
    3. If guardrails return a blocking response, returns it immediately
    4. If guardrails pass, calls the original function
    5. After successful execution, logs the audit result
    """
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        tool_name = fn.__name__
        confirm = kwargs.get("confirm", False)
        dry_run = kwargs.get("dry_run", False)

        # Build parameter dict for guardrail inspection (exclude internal flags)
        params = {}
        sig = inspect.signature(fn)
        for name, param in sig.parameters.items():
            if name in ("confirm", "dry_run"):
                continue
            if name in kwargs:
                params[name] = kwargs[name]
            elif args and list(sig.parameters.keys()).index(name) < len(args):
                params[name] = args[list(sig.parameters.keys()).index(name)]

        # Run all guardrail checks
        block = check_guardrails(tool_name, params, confirm=confirm, dry_run=dry_run)
        if block is not None:
            return block

        # Capture pre-change config revision for rollback
        pre_change_revision = None
        risk = classify_risk(tool_name)
        if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            try:
                from .server import get_api_client as _get_client
                _client = _get_client()
                _hist = await _client.crud_list(
                    "/diagnostics/config_history/revisions",
                    pagination=PaginationOptions(limit=1),
                )
                _revisions = _hist.get("data") or []
                if _revisions:
                    pre_change_revision = {
                        "id": _revisions[0].get("id"),
                        "time": _revisions[0].get("time"),
                        "description": _revisions[0].get("description", ""),
                    }
            except Exception:
                pass  # Non-critical — don't block the operation

        # Guardrails passed — execute the tool
        result = await fn(*args, **kwargs)

        # Post-execution: attach pre-change revision for rollback
        if isinstance(result, dict) and pre_change_revision and result.get("success"):
            result["config_backup"] = {
                "pre_change_revision_id": pre_change_revision["id"],
                "pre_change_time": pre_change_revision["time"],
                "pre_change_description": pre_change_revision["description"],
                "rollback_instruction": (
                    f"To undo this change, call restore_config_backup("
                    f"revision_id={pre_change_revision['id']}, confirm=True)"
                ),
            }
            # Record in rollback buffer
            record_rollback(
                tool_name,
                tool_name.replace("delete_", "").replace("_", " "),
                _extract_object_id(params),
                pre_change_revision,
            )

        # Post-execution audit log
        success = result.get("success", False) if isinstance(result, dict) else True
        audit_log(
            tool_name,
            classify_risk(tool_name),
            params,
            result="success" if success else "failed",
            user_confirmed=confirm,
        )

        return result

    return wrapper
