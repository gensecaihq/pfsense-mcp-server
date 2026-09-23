"""Contract tests for the v1.1.0 release-audit wire fixes.

Each drives a real tool through the mocked client and checks the payload
against the pfSense v2.10.2 model contract. Before the fixes every one of
these was a 400 (or a 404) upstream: SSH/SMTP ports went out as ints (the
models declare strings), ``dnslocalhost`` went out as a bool (an enum of
``local``/``remote``), and the limiter sent a scalar bandwidth plus a
nonexistent ``bandwidthtype`` field while omitting the required ``sched`` and
``aqm``. BIND record search queried a plural endpoint that does not exist.
"""
from src.tools.misc_services import update_ssh_settings
from src.tools.pkg_bind import search_bind_zone_records
from src.tools.system_advanced import update_email_notification_settings
from src.tools.system_settings import update_system_dns
from src.tools.traffic_shaper import create_traffic_limiter, update_traffic_limiter
from tests.contract.schema import assert_payload_valid, capture_call


class TestSettingsPorts:
    async def test_ssh_port_is_string(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await update_ssh_settings(port=2222)
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["port"] == "2222"

    async def test_smtp_port_is_string(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await update_email_notification_settings(
            port=587, username="u", password="p"
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["port"] == "587"


class TestSystemDns:
    async def test_dnslocalhost_is_enum(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await update_system_dns(dnslocalhost="Local")
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data == {"dnslocalhost": "local"}

    async def test_dnslocalhost_rejects_other_values(self, mock_client, mock_make_request):
        result = await update_system_dns(dnslocalhost="true")
        assert result["success"] is False
        mock_make_request.assert_not_called()


class TestTrafficLimiter:
    async def test_create_payload_matches_contract(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await create_traffic_limiter(
            name="guest", bandwidth=50, bandwidthtype="mb", descr="guest cap"
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request, require_create=True)
        _, _, data = capture_call(mock_make_request)
        assert data["bandwidth"] == [{"bw": 50, "bwscale": "Mb"}]
        assert data["sched"] == "wf2q+" and data["aqm"] == "droptail"
        assert "bandwidthtype" not in data and "descr" not in data
        assert data["description"] == "guest cap"

    async def test_gb_is_sent_as_mb(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await create_traffic_limiter(name="wan", bandwidth=1, bandwidthtype="Gb")
        _, _, data = capture_call(mock_make_request)
        assert data["bandwidth"] == [{"bw": 1000, "bwscale": "Mb"}]

    async def test_bad_unit_rejected_before_request(self, mock_client, mock_make_request):
        result = await create_traffic_limiter(name="x", bandwidth=5, bandwidthtype="Tb")
        assert result["success"] is False
        mock_make_request.assert_not_called()

    async def test_update_payload_matches_contract(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await update_traffic_limiter(
            limiter_id=1, bandwidth=10, bandwidthtype="Kb", aqm="codel"
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["bandwidth"] == [{"bw": 10, "bwscale": "Kb"}]
        assert data["aqm"] == "codel"

    async def test_update_needs_bandwidth_and_unit_together(
        self, mock_client, mock_make_request
    ):
        result = await update_traffic_limiter(limiter_id=1, bandwidth=10)
        assert result["success"] is False
        mock_make_request.assert_not_called()


class TestBindZoneRecords:
    async def test_reads_records_embedded_in_zone(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 2, "records": [
            {"name": "www", "type": "A", "rdata": "10.0.0.5"},
            {"name": "mail", "type": "MX", "rdata": "10 mx.example."},
            {"name": "api", "type": "A", "rdata": "10.0.0.6"},
        ]}}
        result = await search_bind_zone_records(parent_id=2, record_type="a")
        assert result["success"] is True
        method, endpoint, _ = capture_call(mock_make_request)
        assert (method, endpoint) == ("GET", "/services/bind/zone")
        assert [r["name"] for r in result["records"]] == ["api", "www"]
        assert result["total_matches"] == 2
