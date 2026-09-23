"""Benchmark: GCF vs JSON token cost on representative pfSense tool results.

The read tools return arrays of uniform records (firewall rules, aliases, DHCP
leases). GCF's generic profile factors the repeated field names into one header,
so the token cost drops on larger result sets. Every payload here round-trips
losslessly through GCF.

    pip install 'pfsense-mcp-server[gcf]' tiktoken
    python benchmarks/gcf_benchmark.py
"""

import json

from gcf import decode_generic, encode_generic

try:
    import tiktoken

    _enc = tiktoken.get_encoding("o200k_base")

    def ntok(s: str) -> int:
        return len(_enc.encode(s))

    UNIT = "o200k tokens"
except Exception:  # noqa: BLE001 - tiktoken optional; fall back to characters

    def ntok(s: str) -> int:
        return len(s)

    UNIT = "characters"


def firewall_rules(n: int) -> dict:
    return {
        "success": True,
        "count": n,
        "rules": [
            {
                "id": i,
                "type": "pass" if i % 4 else "block",
                "interface": "wan",
                "ipprotocol": "inet",
                "protocol": "tcp",
                "source": "any",
                "destination": f"192.168.{i % 4}.0/24",
                "descr": f"allow web tier {i}",
                "disabled": False,
            }
            for i in range(n)
        ],
    }


def aliases(n: int) -> dict:
    return {
        "success": True,
        "count": n,
        "aliases": [
            {
                "name": f"alias_{i:03d}",
                "type": "host",
                "address": f"10.0.{i % 8}.{i % 200}",
                "descr": f"managed host {i}",
            }
            for i in range(n)
        ],
    }


def dhcp_leases(n: int) -> dict:
    return {
        "success": True,
        "count": n,
        "leases": [
            {
                "ip": f"192.168.1.{i + 10}",
                "mac": f"00:11:22:33:{i:02x}:{(i * 7) % 256:02x}",
                "hostname": f"device-{i:03d}",
                "start": "2026-08-16 08:00:00",
                "end": "2026-08-16 20:00:00",
                "state": "active" if i % 3 else "expired",
            }
            for i in range(n)
        ],
    }


def main() -> None:
    print(f"unit: {UNIT}\n")
    for label, payload in [
        ("firewall rules (30)", firewall_rules(30)),
        ("aliases (30)", aliases(30)),
        ("DHCP leases (30)", dhcp_leases(30)),
    ]:
        js = json.dumps(payload)
        wire = encode_generic(payload)
        assert decode_generic(wire) == payload, "round-trip must be lossless"
        tj, tg = ntok(js), ntok(wire)
        pct = 100 * (1 - tg / tj)
        print(f"{label:24s}  JSON {tj:6d} -> GCF {tg:6d}   ({pct:.1f}% fewer, lossless)")


if __name__ == "__main__":
    main()
