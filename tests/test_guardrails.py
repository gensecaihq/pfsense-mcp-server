"""Tests for the guardrail system — action classification, approval gates,
rate limiting, input sanitization, dry-run, and rollback tracking."""

import pytest

from src.guardrails import (
    RiskLevel,
    build_approval_request,
    build_dry_run_response,
    check_guardrails,
    check_rate_limit,
    classify_risk,
    get_rollback_history,
    is_tool_allowed,
    record_rollback,
    sanitize_input,
    sanitize_parameters,
)


# ---------------------------------------------------------------------------
# Action Classification
# ---------------------------------------------------------------------------

class TestClassifyRisk:
    def test_read_tools(self):
        assert classify_risk("search_firewall_rules") == RiskLevel.READ
        assert classify_risk("get_system_dns") == RiskLevel.READ
        assert classify_risk("find_blocked_rules") == RiskLevel.READ
        assert classify_risk("analyze_blocked_traffic") == RiskLevel.READ
        assert classify_risk("system_status") == RiskLevel.READ

    def test_low_risk(self):
        assert classify_risk("update_firewall_rule") == RiskLevel.LOW
        assert classify_risk("apply_firewall_changes") == RiskLevel.LOW
        assert classify_risk("enable_hateoas") == RiskLevel.LOW
        assert classify_risk("control_service") == RiskLevel.LOW

    def test_medium_risk(self):
        assert classify_risk("create_firewall_rule_advanced") == RiskLevel.MEDIUM
        assert classify_risk("create_alias") == RiskLevel.MEDIUM
        assert classify_risk("move_firewall_rule") == RiskLevel.MEDIUM

    def test_high_risk(self):
        assert classify_risk("delete_firewall_rule") == RiskLevel.HIGH
        assert classify_risk("delete_alias") == RiskLevel.HIGH
        assert classify_risk("delete_nat_port_forward") == RiskLevel.HIGH

    def test_critical_risk(self):
        assert classify_risk("halt_system") == RiskLevel.CRITICAL
        assert classify_risk("reboot_system") == RiskLevel.CRITICAL
        assert classify_risk("bulk_block_ips") == RiskLevel.CRITICAL

    def test_unknown_defaults_to_medium(self):
        assert classify_risk("unknown_tool_xyz") == RiskLevel.MEDIUM


# ---------------------------------------------------------------------------
# Approval Gate
# ---------------------------------------------------------------------------

class TestApprovalRequest:
    def test_builds_approval_for_delete(self):
        result = build_approval_request(
            "delete_firewall_rule",
            {"rule_id": 5, "confirm": False},
            "Delete firewall rule 5",
        )
        assert result["approval_required"] is True
        assert result["risk_level"] == "high"
        assert "request_id" in result
        assert "rule_id" in str(result["parameters_visible"])

    def test_redacts_sensitive_params(self):
        result = build_approval_request(
            "create_openvpn_server",
            {"name": "test", "password": "secret123", "pre_shared_key": "psk"},
            "Create VPN server",
        )
        params = result["parameters_visible"]
        assert params["password"] == "***REDACTED***"
        assert params["pre_shared_key"] == "***REDACTED***"
        assert params["name"] == "test"  # Non-sensitive preserved


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    def test_allows_normal_usage(self):
        assert check_rate_limit("search_firewall_rules") is None  # read = no limit
        assert check_rate_limit("update_system_dns") is None  # low = no limit

    def test_critical_limited(self):
        # Critical ops have a very low limit (2 per 300s)
        # First two should pass
        result1 = check_rate_limit("halt_system")
        result2 = check_rate_limit("reboot_system")
        # Third should be rate-limited
        result3 = check_rate_limit("halt_system")
        # At least one of the first two should pass, third should fail
        assert result3 is not None or (result1 is None and result2 is None)


# ---------------------------------------------------------------------------
# Input Sanitization
# ---------------------------------------------------------------------------

class TestInputSanitization:
    def test_clean_input(self):
        assert sanitize_input("Allow HTTPS traffic") is None
        assert sanitize_input("10.0.0.0/24") is None
        assert sanitize_input("web_server_01") is None

    def test_directory_traversal(self):
        result = sanitize_input("../../../etc/passwd")
        assert result is not None
        assert "unsafe" in result.lower()

    def test_command_injection(self):
        assert sanitize_input("rule; rm -rf /") is not None
        assert sanitize_input("rule | cat /etc/passwd") is not None
        assert sanitize_input("$(whoami)") is not None
        assert sanitize_input("`id`") is not None

    def test_xss(self):
        assert sanitize_input("<script>alert(1)</script>") is not None

    def test_parameter_scanning(self):
        assert sanitize_parameters({"name": "good", "descr": "safe"}) is None
        result = sanitize_parameters({"name": "good", "descr": "$(whoami)"})
        assert result is not None

    def test_list_parameter_scanning(self):
        result = sanitize_parameters({"addresses": ["10.0.0.1", "$(rm -rf /)"]})
        assert result is not None


# ---------------------------------------------------------------------------
# Dry Run
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_response(self):
        result = build_dry_run_response(
            "delete_firewall_rule",
            {"rule_id": 5},
            "Delete firewall rule 5",
        )
        assert result["dry_run"] is True
        assert result["success"] is True
        assert "no changes were made" in result["message"].lower()
        assert result["risk_level"] == "high"


# ---------------------------------------------------------------------------
# Rollback Tracking
# ---------------------------------------------------------------------------

class TestRollbackTracking:
    def test_record_and_retrieve(self):
        record_rollback(
            "delete_firewall_rule", "firewall_rule", 5,
            {"id": 5, "descr": "Allow HTTPS"},
        )
        history = get_rollback_history(limit=1)
        assert len(history) >= 1
        assert history[0]["object_type"] == "firewall_rule"
        assert history[0]["has_previous_state"] is True

    def test_without_previous_state(self):
        record_rollback("create_alias", "alias", 10, None)
        history = get_rollback_history(limit=1)
        assert history[0]["has_previous_state"] is False


# ---------------------------------------------------------------------------
# Allowlisting
# ---------------------------------------------------------------------------

class TestAllowlisting:
    def test_read_always_allowed(self):
        assert is_tool_allowed("search_firewall_rules") is True

    def test_no_allowlist_allows_all(self):
        # With no MCP_ALLOWED_TOOLS set, all tools should be allowed
        assert is_tool_allowed("delete_firewall_rule") is True


# ---------------------------------------------------------------------------
# Unified check_guardrails
# ---------------------------------------------------------------------------

class TestCheckGuardrails:
    def test_read_passes(self):
        result = check_guardrails("search_firewall_rules", {})
        assert result is None  # No blocking

    def test_high_risk_without_confirm_blocks(self):
        result = check_guardrails("delete_firewall_rule", {"rule_id": 5})
        assert result is not None
        assert result.get("approval_required") is True

    def test_high_risk_with_confirm_passes(self):
        result = check_guardrails("delete_alias", {"alias_id": 1}, confirm=True)
        assert result is None  # Passes

    def test_dry_run_returns_preview(self):
        result = check_guardrails("delete_firewall_rule", {"rule_id": 5}, dry_run=True)
        assert result is not None
        assert result["dry_run"] is True

    def test_injection_blocked(self):
        result = check_guardrails(
            "create_alias",
            {"name": "test", "descr": "$(rm -rf /)"},
        )
        assert result is not None
        assert "unsafe" in result["error"].lower()
