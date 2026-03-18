"""Unit tests for firewall tools (src/tools/firewall.py)."""

from src.tools.firewall import (
    apply_firewall_changes,
    bulk_block_ips,
    create_firewall_rule_advanced,
    delete_firewall_rule,
    find_blocked_rules,
    get_pf_rules,
    move_firewall_rule,
    search_firewall_rules,
    update_firewall_rule,
)

_search_firewall_rules = search_firewall_rules.fn
_create_firewall_rule_advanced = create_firewall_rule_advanced.fn
_update_firewall_rule = update_firewall_rule.fn
_delete_firewall_rule = delete_firewall_rule.fn
_find_blocked_rules = find_blocked_rules.fn
_move_firewall_rule = move_firewall_rule.fn
_bulk_block_ips = bulk_block_ips.fn
_apply_firewall_changes = apply_firewall_changes.fn
_get_pf_rules = get_pf_rules.fn


# ---------------------------------------------------------------------------
# search_firewall_rules
# ---------------------------------------------------------------------------

class TestSearchFirewallRules:
    async def test_no_filters(self, mock_client, mock_make_request, firewall_rules_response):
        mock_make_request.return_value = firewall_rules_response
        result = await _search_firewall_rules()
        assert result["success"] is True
        assert result["count"] == 2

    async def test_interface_filter(self, mock_client, mock_make_request, firewall_rules_response):
        mock_make_request.return_value = firewall_rules_response
        result = await _search_firewall_rules(interface="lan")
        assert result["success"] is True
        call_kwargs = mock_make_request.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert any(f.field == "interface" and f.value == "lan" for f in filters)

    async def test_multiple_filters(self, mock_client, mock_make_request, firewall_rules_response):
        mock_make_request.return_value = firewall_rules_response
        result = await _search_firewall_rules(
            interface="wan", source_ip="10.0.0.1", rule_type="block"
        )
        assert result["success"] is True
        assert result["filters_applied"]["interface"] == "wan"
        assert result["filters_applied"]["source_ip"] == "10.0.0.1"
        assert result["filters_applied"]["rule_type"] == "block"

    async def test_pagination(self, mock_client, mock_make_request, firewall_rules_response):
        mock_make_request.return_value = firewall_rules_response
        result = await _search_firewall_rules(page=2, page_size=10)
        assert result["page"] == 2
        assert result["page_size"] == 10

    async def test_sort(self, mock_client, mock_make_request, firewall_rules_response):
        mock_make_request.return_value = firewall_rules_response
        result = await _search_firewall_rules(sort_by="interface")
        assert result["success"] is True
        call_kwargs = mock_make_request.call_args
        sort = call_kwargs.kwargs.get("sort") or call_kwargs[1].get("sort")
        assert sort.sort_by == "interface"

    async def test_destination_port_filter(self, mock_client, mock_make_request, firewall_rules_response):
        mock_make_request.return_value = firewall_rules_response
        result = await _search_firewall_rules(destination_port="443")
        assert result["success"] is True
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.value == "443" for f in filters)

    async def test_search_description_filter(self, mock_client, mock_make_request, firewall_rules_response):
        mock_make_request.return_value = firewall_rules_response
        result = await _search_firewall_rules(search_description="Allow")
        assert result["success"] is True
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "descr" and f.value == "Allow" and f.operator == "contains" for f in filters)

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("connection lost")
        result = await _search_firewall_rules()
        assert result["success"] is False
        assert "connection lost" in result["error"]


# ---------------------------------------------------------------------------
# create_firewall_rule_advanced
# ---------------------------------------------------------------------------

class TestCreateFirewallRuleAdvanced:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("create failed")
        result = await _create_firewall_rule_advanced(
            interface="lan", rule_type="pass", protocol="tcp",
            source="any", destination="any",
        )
        assert result["success"] is False
        assert "create failed" in result["error"]

    async def test_basic(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 5}}
        result = await _create_firewall_rule_advanced(
            interface="lan",
            rule_type="pass",
            protocol="tcp",
            source="any",
            destination="any",
            destination_port="443",
        )
        assert result["success"] is True
        call_data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[0][2]
        assert call_data["interface"] == ["lan"]
        assert call_data["protocol"] == "tcp"

    async def test_statetype_included(self, mock_client, mock_make_request):
        """Rules must include statetype for the pf filter compiler."""
        mock_make_request.return_value = {"data": {"id": 5}}
        await _create_firewall_rule_advanced(
            interface="lan", rule_type="pass", protocol="tcp",
            source="any", destination="any",
        )
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["statetype"] == "keep state"

    async def test_protocol_any_maps_to_null(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 6}}
        await _create_firewall_rule_advanced(
            interface="wan", rule_type="block", protocol="any",
            source="any", destination="any",
        )
        data = mock_make_request.call_args[1].get("data") or mock_make_request.call_args.kwargs.get("data")
        assert data["protocol"] is None

    async def test_position_creates_then_moves_then_applies(self, mock_client, mock_make_request):
        """Position creates rule first, then moves it, then forces apply."""
        mock_make_request.return_value = {"data": {"id": 7}}
        await _create_firewall_rule_advanced(
            interface="lan", rule_type="pass", protocol="tcp",
            source="any", destination="any", position=0,
        )
        # Create + move + apply = 3 calls
        assert mock_make_request.call_count == 3
        # First call: create (no placement)
        create_control = mock_make_request.call_args_list[0].kwargs.get("control")
        assert create_control.placement is None
        # Second call: move to position 0
        move_control = mock_make_request.call_args_list[1].kwargs.get("control")
        assert move_control.placement == 0

    async def test_rejects_space_separated_ports(self, mock_client, mock_make_request):
        """Port values like '53 853' must be rejected before hitting the API."""
        result = await _create_firewall_rule_advanced(
            interface="lan", rule_type="pass", protocol="tcp",
            source="any", destination="any", destination_port="53 853",
        )
        assert result["success"] is False
        assert "Invalid destination_port" in result["error"]
        mock_make_request.assert_not_called()

    async def test_rejects_comma_separated_ports(self, mock_client, mock_make_request):
        result = await _create_firewall_rule_advanced(
            interface="lan", rule_type="pass", protocol="tcp",
            source="any", destination="any", destination_port="80, 443",
        )
        assert result["success"] is False
        mock_make_request.assert_not_called()

    async def test_accepts_alias_name(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 8}}
        result = await _create_firewall_rule_advanced(
            interface="lan", rule_type="pass", protocol="tcp",
            source="any", destination="any", destination_port="DNS_ports",
        )
        assert result["success"] is True


# ---------------------------------------------------------------------------
# update_firewall_rule
# ---------------------------------------------------------------------------

class TestUpdateFirewallRule:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("update failed")
        result = await _update_firewall_rule(rule_id=3, description="x")
        assert result["success"] is False
        assert "update failed" in result["error"]

    async def test_partial_update_field_mapping(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 3}}
        result = await _update_firewall_rule(rule_id=3, description="new desc")
        assert result["success"] is True
        assert "descr" in result["fields_updated"]

    async def test_interface_wrapped_in_list(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 3}}
        await _update_firewall_rule(rule_id=3, interface="dmz")
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["interface"] == ["dmz"]

    async def test_no_fields_error(self, mock_client, mock_make_request):
        result = await _update_firewall_rule(rule_id=3)
        assert result["success"] is False
        assert "No fields" in result["error"]

    async def test_rejects_invalid_port(self, mock_client, mock_make_request):
        result = await _update_firewall_rule(rule_id=3, destination_port="53 853")
        assert result["success"] is False
        assert "Invalid destination_port" in result["error"]
        mock_make_request.assert_not_called()

    async def test_rejects_invalid_source_port(self, mock_client, mock_make_request):
        result = await _update_firewall_rule(rule_id=3, source_port="80, 443")
        assert result["success"] is False
        assert "Invalid source_port" in result["error"]
        mock_make_request.assert_not_called()


# ---------------------------------------------------------------------------
# delete_firewall_rule
# ---------------------------------------------------------------------------

class TestDeleteFirewallRule:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("delete failed")
        result = await _delete_firewall_rule(rule_id=5)
        assert result["success"] is False
        assert "delete failed" in result["error"]

    async def test_passes_id_and_applies(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await _delete_firewall_rule(rule_id=5)
        assert result["success"] is True
        assert result["rule_id"] == 5
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["id"] == 5


# ---------------------------------------------------------------------------
# find_blocked_rules
# ---------------------------------------------------------------------------

class TestFindBlockedRules:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("query failed")
        result = await _find_blocked_rules()
        assert result["success"] is False
        assert "query failed" in result["error"]

    async def test_no_interface(self, mock_client, mock_make_request, firewall_rules_response):
        mock_make_request.return_value = firewall_rules_response
        result = await _find_blocked_rules()
        assert result["success"] is True
        assert result["interface_filter"] is None

    async def test_with_interface(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": [
                {"id": 0, "type": "block", "interface": "wan"},
                {"id": 1, "type": "block", "interface": "lan"},
            ],
        }
        result = await _find_blocked_rules(interface="wan")
        assert result["success"] is True
        assert result["interface_filter"] == "wan"
        assert result["count"] == 1


# ---------------------------------------------------------------------------
# move_firewall_rule
# ---------------------------------------------------------------------------

class TestMoveFirewallRule:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("move failed")
        result = await _move_firewall_rule(rule_id=2, new_position=0)
        assert result["success"] is False
        assert "move failed" in result["error"]

    async def test_position_and_apply(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 2}}
        result = await _move_firewall_rule(rule_id=2, new_position=0)
        assert result["success"] is True
        assert result["rule_id"] == 2
        assert result["new_position"] == 0
        # Move PATCH + explicit apply = 2 calls
        assert mock_make_request.call_count == 2

    async def test_no_apply(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 2}}
        result = await _move_firewall_rule(rule_id=2, new_position=0, apply_immediately=False)
        assert result["success"] is True
        # Only the move PATCH, no apply call
        assert mock_make_request.call_count == 1


# ---------------------------------------------------------------------------
# bulk_block_ips
# ---------------------------------------------------------------------------

class TestBulkBlockIps:
    async def test_success(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 10}}
        result = await _bulk_block_ips(ip_addresses=["1.2.3.4", "5.6.7.8"])
        assert result["success"] is True
        assert result["successful"] == 2
        assert result["failed"] == 0

    async def test_all_fail(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("API error")
        result = await _bulk_block_ips(ip_addresses=["1.2.3.4", "5.6.7.8"])
        assert result["success"] is False
        assert result["applied"] is False
        assert result["failed"] == 2
        assert result["successful"] == 0

    async def test_apply_failure(self, mock_client, mock_make_request):
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # First two calls create rules OK, third call (apply) fails
            if call_count <= 2:
                return {"data": {"id": call_count}}
            raise Exception("apply failed")

        mock_make_request.side_effect = side_effect
        result = await _bulk_block_ips(ip_addresses=["1.2.3.4", "5.6.7.8"])
        assert result["successful"] == 2
        assert result["applied"] is False

    async def test_partial_failure(self, mock_client, mock_make_request):
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # First call succeeds (create rule), second fails, third is apply
            if call_count == 2:
                raise Exception("API error")
            return {"data": {"id": call_count}}

        mock_make_request.side_effect = side_effect
        result = await _bulk_block_ips(ip_addresses=["1.2.3.4", "5.6.7.8"])
        assert result["successful"] == 1
        assert result["failed"] == 1

    async def test_statetype_included(self, mock_client, mock_make_request):
        """Bulk block rules must include statetype for pf filter compiler."""
        mock_make_request.return_value = {"data": {"id": 10}}
        await _bulk_block_ips(ip_addresses=["1.2.3.4"])
        # First call is the create, second is the apply
        create_data = mock_make_request.call_args_list[0].kwargs.get("data") or mock_make_request.call_args_list[0][1].get("data")
        assert create_data["statetype"] == "keep state"


# ---------------------------------------------------------------------------
# apply_firewall_changes
# ---------------------------------------------------------------------------

class TestApplyFirewallChanges:
    async def test_success(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"status": "applied"}}
        result = await _apply_firewall_changes()
        assert result["success"] is True
        assert "recompiled" in result["message"]

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("apply failed")
        result = await _apply_firewall_changes()
        assert result["success"] is False
        assert "apply failed" in result["error"]


# ---------------------------------------------------------------------------
# get_pf_rules
# ---------------------------------------------------------------------------

class TestGetPfRules:
    async def test_success(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": "pass in on em0 all\nblock in on em1 all\n"}
        result = await _get_pf_rules()
        assert result["success"] is True
        assert "compiled_rules" in result

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("command failed")
        result = await _get_pf_rules()
        assert result["success"] is False
