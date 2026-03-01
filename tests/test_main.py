"""Unit tests for MCP tool functions in src/main.py.

Every test mocks at the ``_make_request`` level so that filter construction,
pagination, field mapping, and response shaping all get exercised.

FastMCP's @mcp.tool() decorator wraps functions into FunctionTool objects.
We access the underlying coroutine via the ``.fn`` attribute.
"""


import src.main as _main

# Unwrap FunctionTool → raw async function via .fn
system_status = _main.system_status.fn
search_firewall_rules = _main.search_firewall_rules.fn
create_firewall_rule_advanced = _main.create_firewall_rule_advanced.fn
update_firewall_rule = _main.update_firewall_rule.fn
delete_firewall_rule = _main.delete_firewall_rule.fn
search_aliases = _main.search_aliases.fn
create_alias = _main.create_alias.fn
manage_alias_addresses = _main.manage_alias_addresses.fn
search_nat_port_forwards = _main.search_nat_port_forwards.fn
create_nat_port_forward = _main.create_nat_port_forward.fn
delete_nat_port_forward = _main.delete_nat_port_forward.fn
get_firewall_log = _main.get_firewall_log.fn
search_services = _main.search_services.fn
search_dhcp_leases = _main.search_dhcp_leases.fn


# ---------------------------------------------------------------------------
# System status
# ---------------------------------------------------------------------------

class TestSystemStatus:
    async def test_success(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": {"cpu_usage": "5%", "memory_usage": "40%"},
        }
        result = await system_status()
        assert result["success"] is True
        assert "cpu_usage" in result["data"]

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("connection refused")
        result = await system_status()
        assert result["success"] is False
        assert "connection refused" in result["error"]


# ---------------------------------------------------------------------------
# Firewall rules
# ---------------------------------------------------------------------------

class TestSearchFirewallRules:
    async def test_no_filters(self, mock_client, mock_make_request, firewall_rules_response):
        mock_make_request.return_value = firewall_rules_response
        result = await search_firewall_rules()
        assert result["success"] is True
        assert result["count"] == 2

    async def test_interface_filter(self, mock_client, mock_make_request, firewall_rules_response):
        mock_make_request.return_value = firewall_rules_response
        result = await search_firewall_rules(interface="lan")
        assert result["success"] is True
        call_kwargs = mock_make_request.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert any(f.field == "interface" and f.value == "lan" for f in filters)

    async def test_multiple_filters(self, mock_client, mock_make_request, firewall_rules_response):
        mock_make_request.return_value = firewall_rules_response
        result = await search_firewall_rules(
            interface="wan", source_ip="10.0.0.1", rule_type="block"
        )
        assert result["success"] is True
        assert result["filters_applied"]["interface"] == "wan"
        assert result["filters_applied"]["source_ip"] == "10.0.0.1"
        assert result["filters_applied"]["rule_type"] == "block"

    async def test_pagination(self, mock_client, mock_make_request, firewall_rules_response):
        mock_make_request.return_value = firewall_rules_response
        result = await search_firewall_rules(page=2, page_size=10)
        assert result["page"] == 2
        assert result["page_size"] == 10

    async def test_sort(self, mock_client, mock_make_request, firewall_rules_response):
        mock_make_request.return_value = firewall_rules_response
        result = await search_firewall_rules(sort_by="interface")
        assert result["success"] is True
        call_kwargs = mock_make_request.call_args
        sort = call_kwargs.kwargs.get("sort") or call_kwargs[1].get("sort")
        assert sort.sort_by == "interface"


class TestCreateFirewallRuleAdvanced:
    async def test_basic(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 5}}
        result = await create_firewall_rule_advanced(
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

    async def test_protocol_any_maps_to_null(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 6}}
        await create_firewall_rule_advanced(
            interface="wan", rule_type="block", protocol="any",
            source="any", destination="any",
        )
        data = mock_make_request.call_args[1].get("data") or mock_make_request.call_args.kwargs.get("data")
        assert data["protocol"] is None

    async def test_position_placement(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 7}}
        await create_firewall_rule_advanced(
            interface="lan", rule_type="pass", protocol="tcp",
            source="any", destination="any", position=0,
        )
        control = mock_make_request.call_args.kwargs.get("control") or mock_make_request.call_args[1].get("control")
        assert control.placement == 0


class TestUpdateFirewallRule:
    async def test_partial_update_field_mapping(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 3}}
        result = await update_firewall_rule(rule_id=3, description="new desc")
        assert result["success"] is True
        assert "descr" in result["fields_updated"]

    async def test_interface_wrapped_in_list(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 3}}
        await update_firewall_rule(rule_id=3, interface="dmz")
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["interface"] == ["dmz"]

    async def test_no_fields_error(self, mock_client, mock_make_request):
        result = await update_firewall_rule(rule_id=3)
        assert result["success"] is False
        assert "No fields" in result["error"]


class TestDeleteFirewallRule:
    async def test_passes_id_and_applies(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await delete_firewall_rule(rule_id=5)
        assert result["success"] is True
        assert result["rule_id"] == 5
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["id"] == 5


# ---------------------------------------------------------------------------
# Aliases
# ---------------------------------------------------------------------------

class TestSearchAliases:
    async def test_search_by_name(self, mock_client, mock_make_request, aliases_response):
        mock_make_request.return_value = aliases_response
        result = await search_aliases(search_term="blocked")
        assert result["success"] is True
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "name" and f.value == "blocked" for f in filters)

    async def test_filter_by_type(self, mock_client, mock_make_request, aliases_response):
        mock_make_request.return_value = aliases_response
        result = await search_aliases(alias_type="host")
        assert result["success"] is True
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "type" and f.value == "host" for f in filters)


class TestCreateAlias:
    async def test_correct_data(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 2, "name": "test_alias"}}
        result = await create_alias(
            name="test_alias", alias_type="host",
            addresses=["10.0.0.1"], description="Test",
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["name"] == "test_alias"
        assert data["type"] == "host"
        assert data["address"] == ["10.0.0.1"]
        assert data["descr"] == "Test"


class TestManageAliasAddresses:
    async def test_add(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await manage_alias_addresses(
            alias_id=0, action="add", addresses=["10.0.0.3"],
        )
        assert result["success"] is True
        assert result["action"] == "add"

    async def test_remove(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await manage_alias_addresses(
            alias_id=0, action="remove", addresses=["10.0.0.1"],
        )
        assert result["success"] is True
        assert result["action"] == "remove"

    async def test_invalid_action(self, mock_client, mock_make_request):
        result = await manage_alias_addresses(
            alias_id=0, action="purge", addresses=["10.0.0.1"],
        )
        assert result["success"] is False
        assert "add" in result["error"] and "remove" in result["error"]


# ---------------------------------------------------------------------------
# NAT port forwards
# ---------------------------------------------------------------------------

class TestSearchNatPortForwards:
    async def test_basic(self, mock_client, mock_make_request, nat_forwards_response):
        mock_make_request.return_value = nat_forwards_response
        result = await search_nat_port_forwards()
        assert result["success"] is True
        assert result["count"] == 1

    async def test_filters(self, mock_client, mock_make_request, nat_forwards_response):
        mock_make_request.return_value = nat_forwards_response
        result = await search_nat_port_forwards(interface="wan", protocol="tcp")
        assert result["success"] is True
        assert result["filters_applied"]["interface"] == "wan"
        assert result["filters_applied"]["protocol"] == "tcp"


class TestCreateNatPortForward:
    async def test_basic(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 1}}
        result = await create_nat_port_forward(
            interface="wan", protocol="tcp", destination="wanip",
            destination_port="8080", target="192.168.1.50", local_port="80",
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["target"] == "192.168.1.50"

    async def test_associated_rule_id(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 1}}
        await create_nat_port_forward(
            interface="wan", protocol="tcp", destination="wanip",
            destination_port="443", target="192.168.1.50", local_port="443",
            create_associated_rule=False,
        )
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["associated_rule_id"] == ""


class TestDeleteNatPortForward:
    async def test_passes_id(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await delete_nat_port_forward(port_forward_id=3)
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["id"] == 3


# ---------------------------------------------------------------------------
# Services (new tool)
# ---------------------------------------------------------------------------

class TestSearchServices:
    async def test_no_filters(self, mock_client, mock_make_request, services_response):
        mock_make_request.return_value = services_response
        result = await search_services()
        assert result["success"] is True
        assert result["count"] == 3

    async def test_running_filter(self, mock_client, mock_make_request, services_response):
        mock_make_request.return_value = services_response
        result = await search_services(status_filter="running")
        assert result["success"] is True
        mock_make_request.assert_called_once()
        # Verify it called find_running_services path (GET /status/services with running filter)
        call_kwargs = mock_make_request.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert any(f.field == "status" and f.value == "running" for f in filters)

    async def test_stopped_filter(self, mock_client, mock_make_request, services_response):
        mock_make_request.return_value = services_response
        result = await search_services(status_filter="stopped")
        assert result["success"] is True
        call_kwargs = mock_make_request.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert any(f.field == "status" and f.value == "stopped" for f in filters)

    async def test_search_term_with_status(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "status": "ok",
            "code": 200,
            "data": [
                {"name": "dhcpd", "description": "DHCP Server", "status": "running"},
                {"name": "unbound", "description": "DNS Resolver", "status": "running"},
            ],
        }
        result = await search_services(search_term="dhcp", status_filter="running")
        assert result["success"] is True
        # In-memory filter should narrow to just dhcpd
        assert result["count"] == 1
        assert result["services"][0]["name"] == "dhcpd"


# ---------------------------------------------------------------------------
# Firewall log (new tool)
# ---------------------------------------------------------------------------

class TestGetFirewallLog:
    async def test_default(self, mock_client, mock_make_request, firewall_logs_response):
        mock_make_request.return_value = firewall_logs_response
        result = await get_firewall_log()
        assert result["success"] is True
        assert result["count"] == 2

    async def test_lines_capped_at_50(self, mock_client, mock_make_request, firewall_logs_response):
        mock_make_request.return_value = firewall_logs_response
        result = await get_firewall_log(lines=200)
        assert result["lines_requested"] == 50

    async def test_filters(self, mock_client, mock_make_request, firewall_logs_response):
        mock_make_request.return_value = firewall_logs_response
        result = await get_firewall_log(
            action_filter="block", interface="wan",
            source_ip="203.0.113.5", protocol="tcp",
        )
        assert result["success"] is True
        assert result["filters_applied"]["action"] == "block"
        assert result["filters_applied"]["interface"] == "wan"


# ---------------------------------------------------------------------------
# DHCP leases — includes regression test for double-filter bug
# ---------------------------------------------------------------------------

class TestSearchDhcpLeases:
    async def test_basic(self, mock_client, mock_make_request, dhcp_leases_response):
        mock_make_request.return_value = dhcp_leases_response
        result = await search_dhcp_leases()
        assert result["success"] is True
        assert result["count"] == 2

    async def test_interface_filter_appears_once(
        self, mock_client, mock_make_request, dhcp_leases_response
    ):
        """Regression: interface must NOT be passed both via filters AND
        as keyword arg to get_dhcp_leases (which would add it again)."""
        mock_make_request.return_value = dhcp_leases_response
        await search_dhcp_leases(interface="lan")

        # get_dhcp_leases delegates to _make_request. Inspect the filters
        # that _make_request received — "if" should appear exactly once.
        call_kwargs = mock_make_request.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters") or []
        if_count = sum(1 for f in filters if f.field == "if")
        assert if_count == 1, f"Expected 1 'if' filter, got {if_count}"
