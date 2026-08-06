"""Tests for QueryFilter wire serialization.

The pfSense query engine's ``infer_type`` only coerces the lowercase strings
``true``/``false`` to booleans, and its filters use PHP loose ``==`` (any
non-empty string is truthy). So ``str(True)`` -> ``"True"`` silently inverts a
boolean query. These tests pin the corrected serialization.
"""
from src.models import QueryFilter


class TestBooleanSerialization:
    def test_true_lowercases(self):
        assert QueryFilter("disabled", True).to_param() == ("disabled", "true")

    def test_false_lowercases(self):
        # The bug: str(False) == "False", which upstream treats as truthy, so
        # `disabled=False` returned the disabled rules. Must be "false".
        assert QueryFilter("disabled", False).to_param() == ("disabled", "false")

    def test_bool_with_operator(self):
        assert QueryFilter("status", True, "exact").to_param() == ("status", "true")


class TestOtherTypesUnchanged:
    def test_string_passthrough(self):
        assert QueryFilter("name", "wan").to_param() == ("name", "wan")

    def test_int_passthrough(self):
        # int vs numeric-string compares numerically upstream; keep str().
        assert QueryFilter("parent_id", 3).to_param() == ("parent_id", "3")

    def test_operator_suffix(self):
        assert QueryFilter("descr", "web", "contains").to_param() == (
            "descr__contains", "web",
        )
