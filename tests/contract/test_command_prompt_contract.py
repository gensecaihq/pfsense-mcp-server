"""Wire-contract tests for the command sink used by raw log-file reads.

``read_log_file`` is the only caller that builds a *dynamic* command string, so
the payload it POSTs to ``/diagnostics/command_prompt`` is checked against the
real v2.10.2 CommandPrompt model here: ``command`` is the single writable field
and it is required on create.
"""
from tests.contract.schema import (
    assert_payload_valid,
    capture_call,
    check_payload,
    missing_required,
)

COMMAND_PROMPT = "/diagnostics/command_prompt"


class TestCommandPromptContract:
    async def test_read_log_file_payload_matches_contract(
        self, mock_client, mock_make_request
    ):
        mock_make_request.return_value = {"data": {"output": "", "result_code": 0}}
        await mock_client.read_log_file("filter", lines=50)
        assert_payload_valid(mock_make_request, require_create=True)

    async def test_grep_payload_matches_contract(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"output": "", "result_code": 0}}
        await mock_client.read_log_file("auth", lines=50, grep="Failed password")
        assert_payload_valid(mock_make_request, require_create=True)

        _, endpoint, data = capture_call(mock_make_request)
        assert endpoint == COMMAND_PROMPT
        # `command` is a StringField upstream — a list/int would 400 on POST.
        assert isinstance(data["command"], str)

    def test_command_is_required_on_create(self):
        """A payload without `command` is a 400 upstream, so catch it here."""
        assert missing_required("POST", COMMAND_PROMPT, {}) == ["command"]
        assert missing_required(
            "POST", COMMAND_PROMPT, {"command": "tail -n 1 /var/log/system.log"}
        ) == []

    def test_command_must_be_a_string(self):
        violations = check_payload("POST", COMMAND_PROMPT, {"command": 5})
        assert any("command" in v and "integer" in v for v in violations)
