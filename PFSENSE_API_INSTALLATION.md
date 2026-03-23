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

Navigate to **System > REST API** in the pfSense web UI. You should see the REST API settings page with tabs for Settings, Keys, Access Lists, Updates, and Documentation.

### Step 3: Enable Authentication Methods

On the **System > REST API** settings page, configure which authentication methods are active. Multiple methods can be enabled simultaneously.

**Option A: Basic Auth (simplest — recommended for getting started)**
- Enable **Local Database** authentication on the Settings page
- No additional key generation needed — use your existing pfSense admin username and password
- Note: Only local database users are supported (not LDAP/RADIUS)

**Option B: API Key**
- Enable **API Key** authentication on the Settings page
- Go to the **Keys** tab (System > REST API > Keys) to generate a new API key
- The key is tied to the user who creates it and inherits that user's privileges
- Copy the key — you will need it for the MCP server configuration
- Keys can also be generated via `POST /api/v2/auth/key` or revoked via `DELETE /api/v2/auth/key`

**Option C: JWT**
- Enable **JWT** authentication on the Settings page
- Uses your pfSense local database credentials to obtain a short-lived token (default: 1 hour, configurable via `jwt_exp` setting)
- The MCP server handles token retrieval and refresh automatically via `POST /api/v2/auth/jwt`

### Step 4: Assign Privileges

Ensure the API user has appropriate privileges. Go to **System > User Manager**, edit your user, and verify they have the necessary permissions. The admin user has full access by default. For non-admin users, assign privileges matching the API endpoints you need (firewall rules, interfaces, services, etc.).

### Step 5: Optional — Configure Access Controls

On the **System > REST API > Access Lists** tab, you can optionally restrict API access by:
- Source IP address or network
- Specific users
- Time-based schedules

## MCP Server Configuration

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Edit `.env` with your pfSense details. Example using Basic Auth (simplest):

```bash
PFSENSE_URL=https://your-pfsense.local
PFSENSE_USERNAME=admin
PFSENSE_PASSWORD=your-password
PFSENSE_VERSION=PLUS_24_11   # CE_2_8_0, CE_2_8_1, PLUS_24_11, PLUS_25_11
AUTH_METHOD=basic
VERIFY_SSL=false              # Set to true if using a trusted SSL certificate
```

### Authentication Methods

**Basic Auth (simplest — recommended for getting started)**
```bash
AUTH_METHOD=basic
PFSENSE_USERNAME=admin
PFSENSE_PASSWORD=your-password
```

**API Key**
```bash
AUTH_METHOD=api_key
PFSENSE_API_KEY=your-key
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
1. Is `PFSENSE_URL` correct and reachable from this machine?
2. Is the REST API package installed and enabled at **System > REST API**?
3. Is your chosen auth method enabled on the REST API settings page?
4. For `api_key` auth: is the key valid? (generate at System > REST API > Keys)
5. For `basic`/`jwt` auth: are the username and password correct for a local database user?
6. Does the user have sufficient privileges in **System > User Manager**?
7. If using self-signed certs, set `VERIFY_SSL=false`

## Maintenance

The REST API package must be reinstalled after pfSense system upgrades. After upgrading pfSense, re-run the install command with the package matching your new version.

## Resources

- REST API package: https://github.com/pfrest/pfSense-pkg-RESTAPI
- API documentation: https://pfrest.org/
- Interactive Swagger UI: `https://your-pfsense.local/api/v2/documentation`
