"""Tests for two guardrail-honesty fixes: rollback-capture failures are
surfaced (not silently swallowed), and export_* tools are treated as writes."""
from src.guardrails import RiskLevel, classify_risk


class TestExportReclassified:
    def test_export_tools_are_not_read_only(self):
        # A PKCS#12 bundle / OpenVPN profile export POSTs and yields secrets.
        assert classify_risk("export_certificate_pkcs12") == RiskLevel.MEDIUM
        assert classify_risk("export_openvpn_client_config") == RiskLevel.MEDIUM

    async def test_export_tools_are_removed_in_read_only_mode(self):
        # MEDIUM tools are dropped by the read-only filter; confirm they'd be excluded.
        assert classify_risk("export_certificate_pkcs12") != RiskLevel.READ


class TestRollbackHonesty:
    async def test_warning_when_rollback_point_unavailable(
        self, mock_client, mock_make_request
    ):
        """A HIGH-risk tool whose rollback capture yields nothing must say so."""
        from src.tools.firewall import delete_firewall_rule

        assert classify_risk("delete_firewall_rule") == RiskLevel.HIGH
        # Every API call (config-history lookup AND the delete) returns no data,
        # so no pre-change revision can be captured.
        mock_make_request.return_value = {"data": []}
        result = await delete_firewall_rule(rule_id=0, confirm=True)
        assert result.get("success") is True
        assert "config_backup_warning" in result
        assert "rollback" in result["config_backup_warning"].lower()

    async def test_backup_attached_when_revision_available(
        self, mock_client, mock_make_request
    ):
        from src.tools.firewall import delete_firewall_rule

        mock_make_request.return_value = {"data": [{"id": 42, "time": "t", "description": "d"}]}
        result = await delete_firewall_rule(rule_id=0, confirm=True)
        assert result.get("success") is True
        # A real rollback point was captured, so the backup block is present and
        # the "unavailable" warning is not.
        assert "config_backup" in result
        assert "config_backup_warning" not in result
