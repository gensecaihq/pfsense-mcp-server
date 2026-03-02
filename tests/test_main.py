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
find_interfaces_by_status = _main.find_interfaces_by_status.fn
find_blocked_rules = _main.find_blocked_rules.fn
create_firewall_rule_advanced = _main.create_firewall_rule_advanced.fn
update_firewall_rule = _main.update_firewall_rule.fn
delete_firewall_rule = _main.delete_firewall_rule.fn
move_firewall_rule = _main.move_firewall_rule.fn
bulk_block_ips = _main.bulk_block_ips.fn
search_aliases = _main.search_aliases.fn
create_alias = _main.create_alias.fn
update_alias = _main.update_alias.fn
delete_alias = _main.delete_alias.fn
manage_alias_addresses = _main.manage_alias_addresses.fn
search_nat_port_forwards = _main.search_nat_port_forwards.fn
create_nat_port_forward = _main.create_nat_port_forward.fn
update_nat_port_forward = _main.update_nat_port_forward.fn
delete_nat_port_forward = _main.delete_nat_port_forward.fn
get_firewall_log = _main.get_firewall_log.fn
analyze_blocked_traffic = _main.analyze_blocked_traffic.fn
search_logs_by_ip = _main.search_logs_by_ip.fn
search_services = _main.search_services.fn
control_service = _main.control_service.fn
search_dhcp_leases = _main.search_dhcp_leases.fn
search_dhcp_static_mappings = _main.search_dhcp_static_mappings.fn
create_dhcp_static_mapping = _main.create_dhcp_static_mapping.fn
update_dhcp_static_mapping = _main.update_dhcp_static_mapping.fn
delete_dhcp_static_mapping = _main.delete_dhcp_static_mapping.fn
follow_api_link = _main.follow_api_link.fn
enable_hateoas = _main.enable_hateoas.fn
disable_hateoas = _main.disable_hateoas.fn
refresh_object_ids = _main.refresh_object_ids.fn
find_object_by_field = _main.find_object_by_field.fn
get_api_capabilities = _main.get_api_capabilities.fn
test_enhanced_connection = _main.test_enhanced_connection.fn


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


# ---------------------------------------------------------------------------
# Update alias
# ---------------------------------------------------------------------------

class TestUpdateAlias:
    async def test_basic_update(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0, "name": "updated"}}
        result = await update_alias(alias_id=0, name="updated", description="new desc")
        assert result["success"] is True
        assert result["alias_id"] == 0
        assert "name" in result["fields_updated"]
        assert "descr" in result["fields_updated"]

    async def test_partial_fields(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 1}}
        result = await update_alias(alias_id=1, addresses=["10.0.0.5"])
        assert result["success"] is True
        assert "address" in result["fields_updated"]

    async def test_no_fields_error(self, mock_client, mock_make_request):
        result = await update_alias(alias_id=0)
        assert result["success"] is False
        assert "No fields" in result["error"]


# ---------------------------------------------------------------------------
# Delete alias
# ---------------------------------------------------------------------------

class TestDeleteAlias:
    async def test_passes_id_and_applies(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await delete_alias(alias_id=2)
        assert result["success"] is True
        assert result["alias_id"] == 2
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["id"] == 2


# ---------------------------------------------------------------------------
# Update NAT port forward
# ---------------------------------------------------------------------------

class TestUpdateNatPortForward:
    async def test_basic_update(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await update_nat_port_forward(
            port_forward_id=0, target="192.168.1.60", local_port="8080"
        )
        assert result["success"] is True
        assert "target" in result["fields_updated"]
        assert "local_port" in result["fields_updated"]

    async def test_partial_update(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 1}}
        result = await update_nat_port_forward(port_forward_id=1, description="new desc")
        assert result["success"] is True
        assert "descr" in result["fields_updated"]

    async def test_no_fields_error(self, mock_client, mock_make_request):
        result = await update_nat_port_forward(port_forward_id=0)
        assert result["success"] is False
        assert "No fields" in result["error"]

    async def test_interface_wrapped_in_list(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        await update_nat_port_forward(port_forward_id=0, interface="lan")
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["interface"] == ["lan"]


# ---------------------------------------------------------------------------
# Control service
# ---------------------------------------------------------------------------

class TestControlService:
    async def test_start(self, mock_client, mock_make_request, service_control_response):
        mock_make_request.return_value = service_control_response
        result = await control_service(service_name="dhcpd", action="start")
        assert result["success"] is True
        assert result["action"] == "start"
        mock_make_request.assert_called_once()

    async def test_stop(self, mock_client, mock_make_request, service_control_response):
        mock_make_request.return_value = service_control_response
        result = await control_service(service_name="dhcpd", action="stop")
        assert result["success"] is True
        assert result["action"] == "stop"

    async def test_restart(self, mock_client, mock_make_request, service_control_response):
        mock_make_request.return_value = service_control_response
        result = await control_service(service_name="dhcpd", action="restart")
        assert result["success"] is True
        assert result["action"] == "restart"

    async def test_invalid_action(self, mock_client, mock_make_request):
        result = await control_service(service_name="dhcpd", action="purge")
        assert result["success"] is False
        assert "Invalid action" in result["error"]


# ---------------------------------------------------------------------------
# Search DHCP static mappings
# ---------------------------------------------------------------------------

class TestSearchDhcpStaticMappings:
    async def test_no_filters(self, mock_client, mock_make_request, dhcp_static_mappings_response):
        mock_make_request.return_value = dhcp_static_mappings_response
        result = await search_dhcp_static_mappings()
        assert result["success"] is True
        assert result["count"] == 2

    async def test_interface_filter(self, mock_client, mock_make_request, dhcp_static_mappings_response):
        mock_make_request.return_value = dhcp_static_mappings_response
        result = await search_dhcp_static_mappings(interface="lan")
        assert result["success"] is True
        call_kwargs = mock_make_request.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert any(f.field == "parent_id" and f.value == "lan" for f in filters)

    async def test_mac_filter(self, mock_client, mock_make_request, dhcp_static_mappings_response):
        mock_make_request.return_value = dhcp_static_mappings_response
        result = await search_dhcp_static_mappings(mac_address="aa:bb:cc:dd:ee:01")
        assert result["success"] is True
        call_kwargs = mock_make_request.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert any(f.field == "mac" for f in filters)


# ---------------------------------------------------------------------------
# Create DHCP static mapping
# ---------------------------------------------------------------------------

class TestCreateDhcpStaticMapping:
    async def test_required_fields(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await create_dhcp_static_mapping(
            interface="lan", mac_address="aa:bb:cc:dd:ee:03", ip_address="192.168.1.202"
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["parent_id"] == "lan"
        assert data["mac"] == "aa:bb:cc:dd:ee:03"
        assert data["ipaddr"] == "192.168.1.202"

    async def test_all_fields(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 1}}
        result = await create_dhcp_static_mapping(
            interface="lan", mac_address="aa:bb:cc:dd:ee:04",
            ip_address="192.168.1.203", hostname="myhost",
            description="Test mapping", dns_server="8.8.8.8",
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["hostname"] == "myhost"
        assert data["descr"] == "Test mapping"
        assert data["dnsserver"] == "8.8.8.8"


# ---------------------------------------------------------------------------
# Update DHCP static mapping
# ---------------------------------------------------------------------------

class TestUpdateDhcpStaticMapping:
    async def test_partial_update(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await update_dhcp_static_mapping(mapping_id=0, hostname="newhostname")
        assert result["success"] is True
        assert "hostname" in result["fields_updated"]

    async def test_no_fields_error(self, mock_client, mock_make_request):
        result = await update_dhcp_static_mapping(mapping_id=0)
        assert result["success"] is False
        assert "No fields" in result["error"]


# ---------------------------------------------------------------------------
# Delete DHCP static mapping
# ---------------------------------------------------------------------------

class TestDeleteDhcpStaticMapping:
    async def test_passes_id(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await delete_dhcp_static_mapping(mapping_id=3)
        assert result["success"] is True
        assert result["mapping_id"] == 3
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["id"] == 3


# ===========================================================================
# Gap-fill tests for existing untested tools
# ===========================================================================


# ---------------------------------------------------------------------------
# find_interfaces_by_status
# ---------------------------------------------------------------------------

class TestFindInterfacesByStatus:
    async def test_basic(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": [{"name": "wan", "status": "up"}],
        }
        result = await find_interfaces_by_status(status="up")
        assert result["success"] is True
        assert result["status_filter"] == "up"
        assert result["count"] == 1


# ---------------------------------------------------------------------------
# find_blocked_rules
# ---------------------------------------------------------------------------

class TestFindBlockedRules:
    async def test_no_interface(self, mock_client, mock_make_request, firewall_rules_response):
        mock_make_request.return_value = firewall_rules_response
        result = await find_blocked_rules()
        assert result["success"] is True
        assert result["interface_filter"] is None

    async def test_with_interface(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": [
                {"id": 0, "type": "block", "interface": "wan"},
                {"id": 1, "type": "block", "interface": "lan"},
            ],
        }
        result = await find_blocked_rules(interface="wan")
        assert result["success"] is True
        assert result["interface_filter"] == "wan"
        assert result["count"] == 1


# ---------------------------------------------------------------------------
# move_firewall_rule
# ---------------------------------------------------------------------------

class TestMoveFirewallRule:
    async def test_position_and_apply(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 2}}
        result = await move_firewall_rule(rule_id=2, new_position=0)
        assert result["success"] is True
        assert result["rule_id"] == 2
        assert result["new_position"] == 0


# ---------------------------------------------------------------------------
# bulk_block_ips
# ---------------------------------------------------------------------------

class TestBulkBlockIps:
    async def test_success(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 10}}
        result = await bulk_block_ips(ip_addresses=["1.2.3.4", "5.6.7.8"])
        assert result["success"] is True
        assert result["successful"] == 2
        assert result["failed"] == 0

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
        result = await bulk_block_ips(ip_addresses=["1.2.3.4", "5.6.7.8"])
        assert result["successful"] == 1
        assert result["failed"] == 1


# ---------------------------------------------------------------------------
# analyze_blocked_traffic
# ---------------------------------------------------------------------------

class TestAnalyzeBlockedTraffic:
    async def test_grouped(self, mock_client, mock_make_request, firewall_logs_response):
        mock_make_request.return_value = firewall_logs_response
        result = await analyze_blocked_traffic(group_by_source=True)
        assert result["success"] is True
        assert result["analysis"]["grouped_by"] == "source_ip"

    async def test_ungrouped(self, mock_client, mock_make_request, firewall_logs_response):
        mock_make_request.return_value = firewall_logs_response
        result = await analyze_blocked_traffic(group_by_source=False)
        assert result["success"] is True
        assert result["analysis"]["grouped_by"] == "none"
        assert "raw_entries" in result["analysis"]


# ---------------------------------------------------------------------------
# search_logs_by_ip
# ---------------------------------------------------------------------------

class TestSearchLogsByIp:
    async def test_firewall_type(self, mock_client, mock_make_request, firewall_logs_response):
        mock_make_request.return_value = firewall_logs_response
        result = await search_logs_by_ip(ip_address="203.0.113.5", log_type="firewall")
        assert result["success"] is True
        assert result["ip_address"] == "203.0.113.5"
        assert result["patterns"] is not None

    async def test_non_firewall_type(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        result = await search_logs_by_ip(ip_address="10.0.0.1", log_type="system")
        assert result["success"] is True
        assert result["log_type"] == "system"
        assert result["patterns"] is None


# ---------------------------------------------------------------------------
# follow_api_link
# ---------------------------------------------------------------------------

class TestFollowApiLink:
    async def test_basic(self, mock_client, mock_make_request):
        # follow_link uses client.client directly, not _make_request
        from unittest.mock import AsyncMock, MagicMock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": 1}], "_links": {}}
        mock_response.raise_for_status = MagicMock()
        mock_client.client = MagicMock()
        mock_client.client.get = AsyncMock(return_value=mock_response)
        result = await follow_api_link(link_url="/firewall/rules")
        assert result["success"] is True


# ---------------------------------------------------------------------------
# enable/disable HATEOAS
# ---------------------------------------------------------------------------

class TestEnableDisableHateoas:
    async def test_enable(self, mock_client, mock_make_request):
        result = await enable_hateoas()
        assert result["success"] is True
        assert mock_client.hateoas_enabled is True

    async def test_disable(self, mock_client, mock_make_request):
        result = await disable_hateoas()
        assert result["success"] is True
        assert mock_client.hateoas_enabled is False


# ---------------------------------------------------------------------------
# refresh_object_ids
# ---------------------------------------------------------------------------

class TestRefreshObjectIds:
    async def test_basic(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": [{"id": 0}, {"id": 1}]}
        result = await refresh_object_ids(endpoint="/firewall/rules")
        assert result["success"] is True
        assert result["refreshed_count"] == 2


# ---------------------------------------------------------------------------
# find_object_by_field
# ---------------------------------------------------------------------------

class TestFindObjectByField:
    async def test_found(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": [{"id": 3, "name": "blocked_hosts"}]}
        result = await find_object_by_field(
            endpoint="/firewall/aliases", field="name", value="blocked_hosts"
        )
        assert result["success"] is True
        assert result["found"] is True
        assert result["object_id"] == 3

    async def test_not_found(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        result = await find_object_by_field(
            endpoint="/firewall/aliases", field="name", value="nonexistent"
        )
        assert result["success"] is True
        assert result["found"] is False


# ---------------------------------------------------------------------------
# get_api_capabilities
# ---------------------------------------------------------------------------

class TestGetApiCapabilities:
    async def test_basic(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"version": "2.0"}}
        result = await get_api_capabilities()
        assert result["success"] is True
        assert result["api_version"] == "v2"


# ---------------------------------------------------------------------------
# test_enhanced_connection
# ---------------------------------------------------------------------------

class TestTestEnhancedConnection:
    async def test_connected(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"status": "ok"}}
        result = await test_enhanced_connection()
        assert result["success"] is True
        assert result["basic_connection"] is True

    async def test_features_failed(self, mock_client, mock_make_request):
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"data": {"status": "ok"}}  # system status ok
            raise Exception("feature not supported")

        mock_make_request.side_effect = side_effect
        result = await test_enhanced_connection()
        assert result["success"] is True
        failed = [t for t in result["feature_tests"] if t["status"] == "failed"]
        assert len(failed) > 0

    async def test_not_connected(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("connection refused")
        result = await test_enhanced_connection()
        assert result["success"] is False
