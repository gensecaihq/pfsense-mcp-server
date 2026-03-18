# pfSense REST API v2 Audit

**Version**: pfSense MCP Server v5.0.0
**API**: pfSense REST API v2.7.3 (pfrest/pfSense-pkg-RESTAPI)
**Audit Date**: March 2026
**Method**: Verified against the pfSense REST API v2 PHP source code (Endpoint.inc, ContentHandler, model files)

## Endpoint Coverage

### Implemented (Full CRUD)

| API Endpoint | HTTP Methods | MCP Tools | Verified |
|---|---|---|---|
| `/firewall/rules` / `/firewall/rule` | GET, POST, PATCH, DELETE | 9 tools | Yes |
| `/firewall/aliases` / `/firewall/alias` | GET, POST, PATCH, DELETE | 5 tools | Yes |
| `/firewall/nat/port_forwards` / `/firewall/nat/port_forward` | GET, POST, PATCH, DELETE | 4 tools | Yes |
| `/firewall/apply` | POST | `apply_firewall_changes` | Yes |
| `/services/dhcp_server/static_mappings` / `static_mapping` | GET, POST, PATCH, DELETE | 5 tools | Yes |
| `/status/service` | POST | `control_service` | Yes |

### Implemented (Read Only)

| API Endpoint | MCP Tools | Verified |
|---|---|---|
| `/status/system` | `system_status` | Yes |
| `/status/interfaces` | `search_interfaces`, `find_interfaces_by_status` | Yes |
| `/status/services` | `search_services` | Yes |
| `/status/dhcp_server/leases` | `search_dhcp_leases` | Yes |
| `/services/dhcp_servers` / `/services/dhcp_server` | `get_dhcp_server_config`, `update_dhcp_server_config` | Yes |
| `/status/logs/firewall` | `get_firewall_log`, `analyze_blocked_traffic`, `search_logs_by_ip` | Yes |
| `/status/logs/{system,dhcp,openvpn,auth}` | `search_logs_by_ip` (non-firewall types) | Yes |
| `/diagnostics/arp_table` | `get_arp_table` | Yes |
| `/diagnostics/command_prompt` | `get_pf_rules` | Yes |
| `/system/restapi/settings` | `get_api_capabilities` | Yes |

### Not Yet Implemented

| Category | Endpoints | Priority |
|---|---|---|
| Routing | `/routing/gateway`, `/routing/static_route` | High |
| VPN | `/vpn/openvpn/server`, `/vpn/ipsec/phase1`, `/vpn/wireguard` | High |
| DNS | `/services/dns_resolver/*`, `/services/dns_forwarder/*` | Medium |
| Certificates | `/system/certificate/*`, `/system/ca/*` | Medium |
| Users | `/user`, `/user/group`, `/user/auth_server` | Medium |
| NAT Outbound | `/firewall/nat/outbound/*` | Low |
| NAT 1:1 | `/firewall/nat/one_to_one/*` | Low |
| Traffic Shaper | `/firewall/traffic_shaper/*` | Low |
| Virtual IPs | `/firewall/virtual_ip/*` | Low |
| Interfaces Config | `/interface/*`, `/interface/vlan/*` | Low |

## Critical API Behaviors Verified

### Control Parameters in JSON Body

The pfSense API reads `apply`, `placement`, `append`, and `remove` from the JSON request body (`$this->request_data`), NOT from URL query parameters. This server correctly merges them into the body with proper type conversion (strings to booleans/integers).

### Content-Type Header

GET requests and bodyless DELETE requests must NOT send `Content-Type: application/json`. When present, the pfSense `JSONContentHandler` is selected and query string parameters are ignored. This server omits the header on GET and bodyless DELETE.

### Endpoint Plural/Singular Pattern

- GET (list many): plural path (`/firewall/rules`, `/firewall/aliases`)
- POST/PATCH/DELETE (single item): singular path (`/firewall/rule`, `/firewall/alias`)

### DELETE Requires ID in Body

DELETE requests send the object ID in the JSON body, not in the URL path.

### Firewall Rule Interface Field

Firewall rules use `many=true` for the `interface` field, so it must be an array: `["wan"]`. NAT port forwards use `many=false`, so interface is a plain string: `"wan"`.

### Service Control Requires Numeric ID

The `POST /status/service` endpoint requires the service's integer `id` (array index), not the `name` field (which is read-only). This server looks up the ID by name before sending the control request.

### Sort Order Constants

Sort order values must be PHP constant names: `SORT_ASC` and `SORT_DESC` (resolved by `constant()` on the server side).

### Firewall Log Model

The `FirewallLog` model only has a single `text` field containing the raw log line. Per-field filters like `action`, `src_ip`, `dst_ip` do not exist as model fields. This server uses `text__contains` for server-side text matching and client-side post-filtering.

### Log Line Limits

Log retrieval is capped at 50 lines per request to prevent pfSense PHP memory exhaustion (the PHP process typically has ~536MB limit).

### ARP Table Field Names

The ARP table model uses `ip_address` and `mac_address` as field names (not `ip` and `mac`). The internal names in the PHP config are `ip-address` and `mac-address` (with dashes), but the API representation uses underscores.

### JWT Authentication

The `/auth/jwt` endpoint only accepts `BasicAuth`. Credentials must be sent via `Authorization: Basic <base64>` header, not in the JSON body.

### HATEOAS

HATEOAS is a global API setting stored in config, not a per-request toggle. The per-request `?hateoas=true` query parameter is not read by the API.

## Tool Count

| Domain | Tools | Test Count |
|---|---|---|
| Firewall | 9 | ~70 |
| DHCP | 7 | ~35 |
| Utility | 7 | ~20 |
| Aliases | 5 | ~25 |
| NAT | 4 | ~25 |
| System | 4 | ~20 |
| Logs | 3 | ~15 |
| Services | 2 | ~13 |
| **Total** | **41** | **223** |
