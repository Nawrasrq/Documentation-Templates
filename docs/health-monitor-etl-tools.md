# Health Monitor ETL Tools

**Status:** Active
**Short Summary:** This tool monitors the health of third-party APIs that the data engineering team depends on for its ETL pipelines. It runs a series of lightweight authentication and connectivity checks against each API, then records the outcome (success or failure, timing, and any error details) to both a local log file and a centralized SQL Server audit table. The goal is to surface broken integrations early, before downstream ETL jobs fail silently.

---

## Table of Contents

- [Project Information](#project-information)
- [Process Overview](#process-overview)
- [Prerequisites](#prerequisites)
- [Usage](#usage)
- [Main Components](#main-components)
- [Error Handling & Edge Cases](#error-handling--edge-cases)
- [Known Issues / Limitations](#known-issues--limitations)
- [Potential Improvements](#potential-improvements)
- [Related Pages](#related-pages)

---

## Project Information

| Field | Value |
|---|---|
| Language / Tech Stack | Python 3, SQL Server (via SQLAlchemy + pyodbc) |
| Bitbucket Link | [NEEDS REVIEW] |
| Jira Link | [NEEDS REVIEW] |
| Last Verified Date | April 22, 2026 |

### Team Members & Contact Info

| Name | Contact | Role |
|---|---|---|
| [NEEDS REVIEW] | [NEEDS REVIEW] | [NEEDS REVIEW] |

---

## Process Overview

### Input / Extraction

Credentials for each third-party API are loaded from a `.env` file at the project root using `python-dotenv`. The `CredentialManager` class reads the environment variables and groups them into per-API dictionaries so that each health check receives only the credentials it needs.

> **Assumption:** The `.env` file must already exist and be populated with all required variables before the tool runs. See the [Environment Variables](#environment-variables) table below for the full list.

### Transformation / Logic

The `APIHealthMonitor` iterates through a fixed list of API integrations and runs a targeted health check against each one. Depending on the API, this means authenticating via OAuth, calling a lightweight endpoint (such as fetching a single order), or verifying that a download link returns a non-empty response. Each check returns a success/failure flag, an error message (if any), and the elapsed time.

The APIs tested are:

| API Name | Check Type |
|---|---|
| Amazon ECAMZ | OAuth token refresh |
| SmartScout | Username/password login |
| Keepa | API key validation via product lookup |
| Shopify Retail | GraphQL query (fetch one order) |
| Shopify Backend | REST endpoint (fetch one order) |
| Shopify ShadesEyeconic | GraphQL query against store |
| Shopify DesignerEyes | GraphQL query against store |
| Sellerboard ECAMZ | Download link accessibility |
| Sellerboard VCS | Download link accessibility |
| eBay KDAR | OAuth token refresh + Fulfillment API call |
| Easy3PL | Selenium-based login and inventory page verification |

### Output / Loading

Results are written to two destinations:

1. **File logs** -- Each run writes a detailed log to `logs/api_health_monitor/api_health_monitor.log`. The log is overwritten on each run, so it always reflects the most recent execution.
2. **SQL Server audit table** -- Each individual API check inserts a row into `[DE-DWH-PROCESSED].logs.etl_job_execution_log` with the job name, category (`"API Health Check"`), start/end timestamps, execution status, and any error details. This table is shared across ETL tools so that operations can monitor all jobs from a single location.

The `ServerName` column is hardcoded to `de-dc-api-001`, which identifies the machine this tool is expected to run on.

---

## Prerequisites

### Language Version

Python 3 [NEEDS REVIEW -- exact minor version not specified in the project]

### Libraries & Dependencies

Defined in `requirements.txt`:

| Package | Minimum Version | Purpose |
|---|---|---|
| requests | 2.31.0 | HTTP/REST API calls |
| pyodbc | 4.0.39 | ODBC driver for SQL Server connectivity |
| python-dotenv | 1.0.0 | Load `.env` file into environment variables |
| sqlalchemy | 2.0.0 | Database engine and query execution |
| selenium | 4.15.0 | Browser automation for Easy3PL health check |
| webdriver-manager | 4.0.0 | Automatic ChromeDriver installation for Selenium |
| beautifulsoup4 | 4.12.0 | Listed as a dependency [NEEDS REVIEW -- not imported in current codebase] |

### Environment Variables

All credentials are stored in a `.env` file at the project root. **Do not paste actual values into this document.** The `.env` file is gitignored.

| Variable | API | Description |
|---|---|---|
| `AMAZON_CLIENT_ID` | Amazon | OAuth client ID |
| `AMAZON_CLIENT_SECRET` | Amazon | OAuth client secret |
| `REFRESH_TOKEN_ECAMZ_US` | Amazon | Refresh token for ECAMZ US marketplace |
| `SMARTSCOUT_USERNAME` | SmartScout | Login username |
| `SMARTSCOUT_PASSWORD` | SmartScout | Login password |
| `KEEPA_API_KEY` | Keepa | API access key |
| `SHOPIFY_STORE_URL` | Shopify | Store domain (e.g. `store-name.myshopify.com`) |
| `SHOPIFY_ACCESS_TOKEN` | Shopify | Retail / GraphQL access token |
| `SHOPIFY_BACKEND_ACCESS_TOKEN` | Shopify | Backend REST API access token |
| `SHADESEYECONIC_DOMAIN` | Shopify (ShadesEyeconic) | Store domain |
| `SHADESEYECONIC_TOKEN` | Shopify (ShadesEyeconic) | Access token |
| `DESIGNEREYES_DOMAIN` | Shopify (DesignerEyes) | Store domain |
| `DESIGNEREYES_TOKEN` | Shopify (DesignerEyes) | Access token |
| `SB_ECAMZ_30D_LINK` | Sellerboard | ECAMZ 30-day data download link |
| `SB_VCS_30D_LINK` | Sellerboard | VCS 30-day data download link |
| `EBAY_APP_ID_PRODUCTION` | eBay | Production application ID |
| `EBAY_CERT_ID_PRODUCTION` | eBay | Production certificate ID |
| `REDIRECT_URL_PRODUCTION` | eBay | OAuth redirect URL |
| `ACCESS_TOKEN_PRODUCTION` | eBay | Current access token (auto-refreshed) |
| `ACCESS_TOKEN_EXPIRES_AT_PRODUCTION` | eBay | Token expiration timestamp (auto-updated) |
| `REFRESH_TOKEN_PRODUCTION` | eBay | Long-lived refresh token |
| `REFRESH_TOKEN_EXPIRES_AT_PRODUCTION` | eBay | Refresh token expiration timestamp |
| `EASY3PL_USERNAME` | Easy3PL | Web portal login username |
| `EASY3PL_PASSWORD` | Easy3PL | Web portal login password |
| `SQL_PROCESSED_CONN` | Database | SQLAlchemy connection string for SQL Server |

### Permissions & Access

- **SQL Server**: The connection string in `SQL_PROCESSED_CONN` must have INSERT permission on `[DE-DWH-PROCESSED].logs.etl_job_execution_log`.
- **ODBC Driver**: An ODBC driver for SQL Server (e.g. ODBC Driver 17 or 18) must be installed on the host machine.
- **Chrome / ChromeDriver**: The Easy3PL check uses Selenium with headless Chrome. Google Chrome must be installed; `webdriver-manager` handles the ChromeDriver binary automatically.
- **Network access**: The machine must be able to reach all third-party API endpoints and the SQL Server instance.

---

## Usage

### Environment Setup

> **Assumption:** Python 3 and `git` are already installed on the machine.

1. Clone the repository and navigate into the project directory.

2. Create and activate a virtual environment:

```bat
python -m venv venv
venv\Scripts\activate.bat
```

3. Install dependencies:

```bat
pip install -r requirements.txt
```

4. Create a `.env` file in the project root and populate all variables listed in the [Environment Variables](#environment-variables) table. Credentials are stored in the team password manager -- do not commit the `.env` file.

### How to Run

| Field | Value |
|---|---|
| Entry point | `main/main.py` |
| Run from | Project root directory |
| PYTHONPATH | Must be set to the project root |

```bat
set PYTHONPATH=%cd%
python main/main.py
```

The batch file `main/main.bat` automates the full sequence (git pull, activate venv, install deps, run). It pulls the latest code before executing so that scheduled runs always use the most recent version:

```bat
main\main.bat
```

### Scheduling

| Field | Value |
|---|---|
| Tool | Windows Task Scheduler [NEEDS REVIEW] |
| Frequency & Time | [NEEDS REVIEW] |
| Typical Runtime | [NEEDS REVIEW] |

> **Assumption:** The Windows Task Scheduler task has already been configured to run `main.bat` from the project root directory. See [Related Pages](#related-pages) for setup instructions.

---

## Main Components

### Key Files / Structure

```
health-monitor-etl-tools/
├── main/
│   ├── main.py            # Entry point
│   └── main.bat           # Windows batch runner for scheduled execution
├── scripts/
│   ├── base.py            # Abstract base class shared by all scripts
│   └── api_health_monitor.py  # Orchestrates all API health checks
├── utils/
│   ├── api.py             # HTTP/GraphQL helpers and per-API test methods
│   ├── credentials.py     # Reads and groups environment variables per API
│   └── db.py              # SQLAlchemy engine management and audit log insertion
├── logs/                  # Created at runtime (gitignored)
├── .env                   # Credentials (gitignored)
├── .gitignore
└── requirements.txt
```

### Key Functions & Classes

**`Base`** (`scripts/base.py`) -- Abstract base class that every script inherits from. It exists so that scripts do not need to duplicate the boilerplate of setting up logging, loading environment variables, and wiring up the `DB`, `API`, and `CredentialManager` utilities. It also exposes wrapper methods for credentials and API tests, which means the orchestrator (`APIHealthMonitor`) can call `self.test_amazon_api(...)` directly without reaching into utility internals.

**`APIHealthMonitor`** (`scripts/api_health_monitor.py`) -- The only concrete script in the project. Its `monitor()` method loads credentials for all APIs, iterates through the test cases, calls `test_api_health()` for each one, and logs the result to the database. The `main()` method wraps `monitor()` with top-level error handling and cleanup (`dispose()`).

**`API`** (`utils/api.py`) -- Provides generic `make_rest_request()` and `make_graphql_request()` methods with built-in timeout, response validation, and timing. Also contains per-API test methods (e.g. `test_amazon_api`, `test_ebay_api`) that know the specific endpoints and expected response shapes for each integration. The eBay check includes automatic token refresh logic that writes new tokens back to `.env`.

**`CredentialManager`** (`utils/credentials.py`) -- Reads environment variables and returns them as structured dictionaries grouped by API. This keeps credential logic centralized: if an API's authentication changes, only this class and the corresponding test method in `API` need to be updated.

**`DB`** (`utils/db.py`) -- Manages SQLAlchemy engines with connection pooling. The `update_etl_job_execution_log()` method inserts a row into the shared audit table. The class uses lazy engine creation so a connection is only opened when the first database write occurs.

### Configuration Files

| File | What It Controls |
|---|---|
| `.env` | All API credentials and the SQL Server connection string |
| `requirements.txt` | Python package dependencies and minimum versions |
| `.gitignore` | Excludes `.env`, `__pycache__`, `*.log`, and other artifacts from version control |

### Logging

- **File logs** are written to `logs/api_health_monitor/api_health_monitor.log` using Python's `logging` module. The file handler uses `mode='w'`, so the log is replaced on each run.
- **Log format:** `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- **Console output:** `main.py` prints a start banner, a completion message, and a summary line (`X/Y APIs are healthy`).

---

## Error Handling & Edge Cases

- If a single API check fails (exception or non-success response), the failure is caught, logged to both file and database, and the monitor continues to the next API. One broken integration does not block the others.
- If credential loading fails (missing environment variable), a `ValueError` is raised with the name of the missing key. This halts the run because credentials are loaded upfront for all APIs.
- If the database is unreachable, the `update_etl_job_execution_log` call will raise a `SQLAlchemyError`. The error propagates up and the run fails.
- The eBay token refresh logic writes updated tokens back to `.env`. If the file write fails, a warning is logged but the check still proceeds with the refreshed token in memory.
- The `dispose()` method in `Base` cleans up logging handlers and database engines. It runs in a `finally` block so resources are released even on failure.

---

## Known Issues / Limitations

- `main.bat` writes its log to `logs\id_status_cleaner.log`, which appears to be a leftover name from a different script. [NEEDS REVIEW -- should this be renamed to match the project?]
- `beautifulsoup4` is listed in `requirements.txt` but is not imported anywhere in the current codebase. [NEEDS REVIEW -- can this dependency be removed?]
- The Easy3PL health check uses Selenium with headless Chrome, which is heavier and slower than the REST-based checks. It also depends on Chrome being installed on the host.
- File logs are overwritten on each run (`mode='w'`), so historical log data is only preserved in the SQL Server audit table.
- The `ServerName` value (`de-dc-api-001`) is hardcoded in `db.py` rather than read from configuration.

---

## Potential Improvements

- Rename the batch file log path to match the project name.
- Add a configurable retry mechanism for transient API failures.
- Replace the Easy3PL Selenium check with a REST-based alternative if one becomes available.
- Make the `ServerName` configurable via environment variable.
- Add a `--dry-run` flag that runs checks but skips the database write.
- Preserve historical file logs (e.g. rotate by date) instead of overwriting.

---

## Related Pages

- [NEEDS REVIEW -- populate as related documentation is created. Examples: ETL job execution log table documentation, scheduling runbook, credential rotation guide.]
