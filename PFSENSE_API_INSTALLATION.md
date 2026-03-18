# pfSense REST API v2 Installation Guide

## Supported Versions

| pfSense Version | REST API Package | Install Command |
|---|---|---|
| pfSense CE 2.8.1 | v2.7.3 | `pkg-static add https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/latest/download/pfSense-2.8.1-pkg-RESTAPI.pkg` |
| pfSense Plus 25.11 | v2.7.3 | `pkg-static -C /dev/null add https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/latest/download/pfSense-25.11-pkg-RESTAPI.pkg` |
| pfSense CE 2.8.0 | v2.6.0+ | Use the 2.8.0 package from [releases](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases) |
| pfSense Plus 24.11 | v2.6.0+ | Use the 24.11 package from [releases](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases) |

Only amd64 (64-bit) builds are supported. Check https://github.com/pfrest/pfSense-pkg-RESTAPI/releases for the correct package matching your exact pfSense version.

## Installation

### Step 1: Install the Package

SSH into your pfSense system and run the install command for your version (see table above). Example for CE 2.8.1:

```bash
pkg-static add https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/latest/download/pfSense-2.8.1-pkg-RESTAPI.pkg
```

### Step 2: Verify Installation

Navigate to **System > REST API** in the pfSense web UI. You should see the REST API settings page with a Swagger documentation link.

### Step 3: Generate an API Key

1. Go to **System > User Manager**
2. Edit the user that will access the API
3. Scroll to **API Keys** and generate a new key
4. Copy the key — you will need it for the MCP server configuration

### Step 4: Assign Privileges

Ensure the API user has appropriate privileges:
- **System: REST API** — base API access
- **Firewall: Rules** — for firewall management
- **Interfaces** — for interface status
- **Services** — for service control

## MCP Server Configuration

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Edit `.env` with your pfSense details:

```bash
PFSENSE_URL=https://your-pfsense.local
PFSENSE_API_KEY=your-generated-api-key
PFSENSE_VERSION=CE_2_8_0   # CE_2_8_0, CE_2_8_1, PLUS_24_11, PLUS_25_11
AUTH_METHOD=api_key
VERIFY_SSL=true
```

### Authentication Methods

**API Key (recommended)**
```bash
AUTH_METHOD=api_key
PFSENSE_API_KEY=your-key
```

**Basic Auth**
```bash
AUTH_METHOD=basic
PFSENSE_USERNAME=admin
PFSENSE_PASSWORD=your-password
```

**JWT**
```bash
AUTH_METHOD=jwt
PFSENSE_USERNAME=admin
PFSENSE_PASSWORD=your-password
```

Note: JWT auth obtains a token via `POST /api/v2/auth/jwt` using Basic Auth credentials, then uses the token as a Bearer header for subsequent requests.

## Test Connection

```bash
python -m src.main
```

The server tests the API connection on startup. If it fails, check:
1. Is `PFSENSE_URL` correct and reachable?
2. Is the REST API package installed and enabled?
3. Is the API key correct and the user has privileges?
4. If using self-signed certs, set `VERIFY_SSL=false` for testing

## Maintenance

The REST API package must be reinstalled after pfSense system upgrades. After upgrading pfSense, re-run the install command with the package matching your new version.

## Resources

- REST API package: https://github.com/pfrest/pfSense-pkg-RESTAPI
- API documentation: https://pfrest.org/
- Interactive Swagger UI: `https://your-pfsense.local/api/v2/documentation`
