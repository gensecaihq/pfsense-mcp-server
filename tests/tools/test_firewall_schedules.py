"""Unit tests for firewall schedule tools (src/tools/firewall_schedules.py)."""

from src.tools.firewall_schedules import (
    create_firewall_schedule,
    create_schedule_time_range,
    update_schedule_time_range,
)

_create_firewall_schedule = create_firewall_schedule.fn
_create_schedule_time_range = create_schedule_time_range.fn
_update_schedule_time_range = update_schedule_time_range.fn


# ---------------------------------------------------------------------------
# create_firewall_schedule
# ---------------------------------------------------------------------------

class TestCreateFirewallSchedule:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("create failed")
        result = await _create_firewall_schedule(
            name="test_sched", hour="8:00-17:00", position=[1, 2, 3],
        )
        assert result["success"] is False
        assert "create failed" in result["error"]

    async def test_timerange_included(self, mock_client, mock_make_request):
        """The API rejects schedules without a timerange; the initial range
        must be sent inline with the create request."""
        mock_make_request.return_value = {"data": {"id": 0, "name": "biz"}}
        result = await _create_firewall_schedule(
            name="biz", hour="8:00-17:00", position=[1, 2, 3, 4, 5],
            rangedescr="weekdays",
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[0][2]
        assert data["timerange"] == [{
            "hour": "8:00-17:00",
            "position": [1, 2, 3, 4, 5],
            "rangedescr": "weekdays",
        }]

    async def test_month_day_range(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0, "name": "xmas"}}
        result = await _create_firewall_schedule(
            name="xmas", hour="0:00-23:59", month=[12], day=[25],
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[0][2]
        assert data["timerange"][0]["month"] == [12]
        assert data["timerange"][0]["day"] == [25]

    async def test_requires_position_or_month_day(self, mock_client, mock_make_request):
        result = await _create_firewall_schedule(name="bad", hour="8:00-17:00")
        assert result["success"] is False
        assert "position" in result["error"]
        mock_make_request.assert_not_called()

    async def test_month_without_day_rejected(self, mock_client, mock_make_request):
        result = await _create_firewall_schedule(
            name="bad", hour="8:00-17:00", month=[12],
        )
        assert result["success"] is False
        mock_make_request.assert_not_called()


# ---------------------------------------------------------------------------
# create_schedule_time_range / update_schedule_time_range
# ---------------------------------------------------------------------------

class TestScheduleTimeRanges:
    async def test_create_position_array_threaded_through(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 1}}
        result = await _create_schedule_time_range(
            parent_id=0, position=[6, 7], hour="9:00-12:00",
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[0][2]
        assert data["position"] == [6, 7]
        assert data["hour"] == "9:00-12:00"

    async def test_update_month_day_arrays(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 1}}
        result = await _update_schedule_time_range(
            time_range_id=1, month=[1, 7], day=[1, 4],
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["month"] == [1, 7]
        assert data["day"] == [1, 4]
