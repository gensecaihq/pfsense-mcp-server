"""Tests for helpers.py — MAC normalization, filterlog parser, alias address validation,
pagination bounds, description sanitization, safe_data helpers."""

import pytest

from src.helpers import (
    MAX_OFFSET,
    MAX_PAGE,
    create_pagination,
    normalize_mac_address,
    parse_filterlog_entry,
    safe_data_dict,
    safe_data_list,
    sanitize_description,
    validate_alias_addresses,
    validate_mac_address,
)


# ---------------------------------------------------------------------------
# MAC address normalization
# ---------------------------------------------------------------------------

class TestNormalizeMacAddress:
    def test_colon_format(self):
        assert normalize_mac_address("AA:BB:CC:DD:EE:FF") == "aa:bb:cc:dd:ee:ff"

    def test_hyphen_format(self):
        assert normalize_mac_address("AA-BB-CC-DD-EE-FF") == "aa:bb:cc:dd:ee:ff"

    def test_bare_format(self):
        assert normalize_mac_address("AABBCCDDEEFF") == "aa:bb:cc:dd:ee:ff"

    def test_lowercase_input(self):
        assert normalize_mac_address("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:dd:ee:ff"

    def test_strips_whitespace(self):
        assert normalize_mac_address("  AA:BB:CC:DD:EE:FF  ") == "aa:bb:cc:dd:ee:ff"

    def test_invalid_too_short(self):
        with pytest.raises(ValueError, match="Invalid MAC"):
            normalize_mac_address("AA:BB:CC")

    def test_invalid_chars(self):
        with pytest.raises(ValueError, match="Invalid MAC"):
            normalize_mac_address("GG:HH:II:JJ:KK:LL")

    def test_invalid_empty(self):
        with pytest.raises(ValueError, match="Invalid MAC"):
            normalize_mac_address("")


class TestValidateMacAddress:
    def test_valid_colon(self):
        assert validate_mac_address("aa:bb:cc:dd:ee:ff") is None

    def test_valid_hyphen(self):
        assert validate_mac_address("aa-bb-cc-dd-ee-ff") is None

    def test_valid_bare(self):
        assert validate_mac_address("aabbccddeeff") is None

    def test_invalid(self):
        result = validate_mac_address("xyz")
        assert result is not None
        assert "Invalid MAC" in result


# ---------------------------------------------------------------------------
# Filterlog parser
# ---------------------------------------------------------------------------

class TestParseFilterlogEntry:
    # Real pfSense filterlog IPv4 TCP line
    SAMPLE_IPV4 = (
        "Jan 15 10:00:00 pfSense filterlog[12345]: "
        "5,,,1000000103,wan,match,block,in,4,0x0,,128,12345,0,none,6,tcp,60,"
        "203.0.113.5,192.168.1.1,54321,22,0,S,"
    )

    # IPv6 filterlog line
    SAMPLE_IPV6 = (
        "Jan 15 10:01:00 pfSense filterlog[12345]: "
        "6,,,1000000104,wan,match,block,in,6,0x00,0x00000,64,tcp,6,40,"
        "2001:db8::1,2001:db8::2,54321,443"
    )

    def test_ipv4_parsing(self):
        result = parse_filterlog_entry(self.SAMPLE_IPV4)
        assert result is not None
        assert result["action"] == "block"
        assert result["interface"] == "wan"
        assert result["direction"] == "in"
        assert result["ip_version"] == "4"
        assert result["src_ip"] == "203.0.113.5"
        assert result["dst_ip"] == "192.168.1.1"
        assert result["src_port"] == "54321"
        assert result["dst_port"] == "22"

    def test_ipv6_parsing(self):
        result = parse_filterlog_entry(self.SAMPLE_IPV6)
        assert result is not None
        assert result["ip_version"] == "6"
        assert result["src_ip"] == "2001:db8::1"
        assert result["dst_ip"] == "2001:db8::2"

    def test_empty_string(self):
        assert parse_filterlog_entry("") is None

    def test_none(self):
        assert parse_filterlog_entry(None) is None

    def test_non_filterlog_line(self):
        assert parse_filterlog_entry("Some random log message") is None

    def test_malformed_short_csv(self):
        result = parse_filterlog_entry("Jan 15 pfSense filterlog[1]: a,b,c")
        assert result is None

    def test_filterlog_without_enough_fields(self):
        result = parse_filterlog_entry(
            "Jan 15 pfSense filterlog[1]: 1,2,3,4,5,6,7,8,4"
        )
        assert result is not None
        assert result["action"] == "7"
        assert result["ip_version"] == "4"
        # Not enough fields for full IPv4 parsing, but shouldn't crash


# ---------------------------------------------------------------------------
# Alias address validation
# ---------------------------------------------------------------------------

class TestValidateAliasAddresses:
    def test_host_with_valid_ips(self):
        assert validate_alias_addresses("host", ["10.0.0.1", "192.168.1.1"]) is None

    def test_host_with_alias_name(self):
        assert validate_alias_addresses("host", ["my_alias"]) is None

    def test_host_rejects_cidr(self):
        result = validate_alias_addresses("host", ["10.0.0.0/24"])
        assert result is not None
        assert "Invalid host" in result

    def test_host_rejects_port(self):
        result = validate_alias_addresses("host", ["443"])
        assert result is not None

    def test_network_with_valid_cidrs(self):
        assert validate_alias_addresses("network", ["10.0.0.0/24", "192.168.0.0/16"]) is None

    def test_network_with_single_ip(self):
        # ip_network accepts single IPs (treated as /32)
        assert validate_alias_addresses("network", ["10.0.0.1"]) is None

    def test_network_rejects_garbage(self):
        result = validate_alias_addresses("network", ["not-a-network"])
        assert result is not None

    def test_port_with_valid_ports(self):
        assert validate_alias_addresses("port", ["443", "80-8080"]) is None

    def test_port_with_alias_name(self):
        assert validate_alias_addresses("port", ["web_ports"]) is None

    def test_port_rejects_invalid(self):
        result = validate_alias_addresses("port", ["99999"])
        assert result is not None

    def test_url_with_valid_urls(self):
        assert validate_alias_addresses("url", ["https://example.com/list.txt"]) is None

    def test_url_rejects_bare_domain(self):
        result = validate_alias_addresses("url", ["example.com"])
        assert result is not None
        assert "http" in result.lower()

    def test_empty_list(self):
        result = validate_alias_addresses("host", [])
        assert result is not None
        assert "empty" in result.lower()

    def test_empty_entry(self):
        result = validate_alias_addresses("host", ["10.0.0.1", ""])
        assert result is not None
        assert "empty" in result.lower()


# ---------------------------------------------------------------------------
# Pagination bounds
# ---------------------------------------------------------------------------

class TestPaginationBounds:
    def test_normal_page(self):
        p, page, size = create_pagination(1, 50)
        assert p.offset == 0
        assert p.limit == 50
        assert page == 1

    def test_extreme_page_capped(self):
        p, page, size = create_pagination(999999, 200)
        assert page == MAX_PAGE
        assert p.offset <= MAX_OFFSET

    def test_negative_page_clamped(self):
        p, page, size = create_pagination(-5, 200)
        assert page == 1
        assert p.offset == 0

    def test_zero_page_size_defaults(self):
        p, page, size = create_pagination(1, 0)
        assert size == 50

    def test_max_page_boundary(self):
        p, page, size = create_pagination(MAX_PAGE, 200)
        assert page == MAX_PAGE
        assert p.offset == (MAX_PAGE - 1) * 200


# ---------------------------------------------------------------------------
# Description sanitization
# ---------------------------------------------------------------------------

class TestSanitizeDescription:
    def test_normal_string(self):
        assert sanitize_description("Allow HTTPS traffic") == "Allow HTTPS traffic"

    def test_truncates_long_string(self):
        long = "a" * 2000
        result = sanitize_description(long)
        assert len(result) == 1024

    def test_strips_control_chars(self):
        result = sanitize_description("hello\x00world\x01test")
        assert "\x00" not in result
        assert "\x01" not in result
        assert "helloworld" in result

    def test_keeps_newlines_and_tabs(self):
        result = sanitize_description("line1\nline2\ttab")
        assert "\n" in result
        assert "\t" in result


# ---------------------------------------------------------------------------
# safe_data_dict / safe_data_list
# ---------------------------------------------------------------------------

class TestSafeDataHelpers:
    def test_safe_data_dict_normal(self):
        assert safe_data_dict({"data": {"id": 1}}) == {"id": 1}

    def test_safe_data_dict_none(self):
        assert safe_data_dict({"data": None}) == {}

    def test_safe_data_dict_string(self):
        assert safe_data_dict({"data": "error"}) == {}

    def test_safe_data_dict_missing(self):
        assert safe_data_dict({}) == {}

    def test_safe_data_dict_non_dict_input(self):
        assert safe_data_dict(None) == {}

    def test_safe_data_list_normal(self):
        assert safe_data_list({"data": [{"id": 1}]}) == [{"id": 1}]

    def test_safe_data_list_none(self):
        assert safe_data_list({"data": None}) == []

    def test_safe_data_list_dict_instead(self):
        assert safe_data_list({"data": {"id": 1}}) == []

    def test_safe_data_list_missing(self):
        assert safe_data_list({}) == []


# ---------------------------------------------------------------------------
# Filterlog IP validation in positional parse
# ---------------------------------------------------------------------------

class TestFilterlogIpValidation:
    def test_invalid_ip_in_src_position(self):
        """If field at src_ip position is not a valid IP, it should be empty."""
        line = (
            "Jan 15 pfSense filterlog[1]: "
            "5,,,1000,wan,match,block,in,4,0x0,,128,12345,0,none,6,tcp,60,"
            "NOT_AN_IP,192.168.1.1,54321,22,0,S,"
        )
        result = parse_filterlog_entry(line)
        assert result is not None
        assert result["src_ip"] == ""
        assert result["dst_ip"] == "192.168.1.1"

    def test_valid_ips_pass_through(self):
        line = (
            "Jan 15 pfSense filterlog[1]: "
            "5,,,1000,wan,match,block,in,4,0x0,,128,12345,0,none,6,tcp,60,"
            "10.0.0.1,10.0.0.2,54321,22,0,S,"
        )
        result = parse_filterlog_entry(line)
        assert result["src_ip"] == "10.0.0.1"
        assert result["dst_ip"] == "10.0.0.2"
