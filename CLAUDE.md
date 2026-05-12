# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (local)
pip install -r requirements.txt

# Run development server
python -m uvicorn app:app --reload

# Run production server
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4

# Prepare offline packages for Linux deployment (run in Docker python:3.9)
pip download -r requirements.txt -d packages

# Install from offline packages (on Linux server)
pip install --no-index --find-links=packages -r requirements.txt

# Generate a secure API key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Environment Setup

Copy `.env.example` to `.env` and fill in:
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DATABASE`
- `SQLSERVER_SERVER`, `SQLSERVER_UID`, `SQLSERVER_PASSWORD`, `SQLSERVER_DATABASE`, `SQLSERVER_SCHEME`
- `API_KEY` (minimum 20 characters)
- `ALLOWED_ORIGINS` (comma-separated list of allowed hosts/origins)

`config.py` validates all required vars at startup and will raise `ValueError` if any are missing.

## Architecture

The entire application lives in `app.py`. There are no sub-modules — all endpoint handlers, database helpers, and business logic are in one file.

### Dual-database design

- **PostgreSQL** (`psycopg2`): Stores historical contractual rules across 5 views (medicamentos, materiais, diárias/taxas, HM/SADT, pacotes). This is the primary data source.
- **SQL Server** (`pyodbc` + ODBC Driver 17): Stores protocol control records (`ZG_CONTROLEPROTOCOLO`) — who locked a protocol and when. This data is merged into `/list` results in memory using a Python dict join (not a SQL join) to avoid ODBC parameter limits.

### TABLE_CONFIGS

`TABLE_CONFIGS` in `app.py` is a dict of `TableConfig` dataclasses, one per PostgreSQL view. Each config defines:
- `business_key`: The list of columns that uniquely identify a row (used as the diff key)
- `columns`: The SELECT clause with aliases matching the business key names
- `ignore_columns`: Columns excluded from change detection (audit/metadata fields)
- `order_by`: Snapshot load order

When modifying table columns or aliases, keep `business_key` names in sync with the column aliases in `columns`.

### Diff algorithm

`/diff` compares two protocol snapshots:
1. `load_snapshot()` builds `Dict[business_key_string, row_data]` per protocol
2. `diff_snapshots()` performs set arithmetic on the key sets to find inserted/deleted rows, then column-by-column comparison for updated rows
3. `ignore_columns` (audit metadata) are skipped during update detection
4. Results are sorted by the business key tokens

### Security

All endpoints require `X-API-Key` header (validated via `verify_api_key` dependency in `security.py`). Input sanitization functions (`validate_protocolo`, `validate_scope`, `validate_filter_list`) are applied to all query parameters before use.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/filters` | Returns distinct filter values across all 5 views |
| GET | `/list` | Lists protocols; accepts `contrato_regional`, `contrato_nome_prestador`, `contrato_nome_operadora` filters; merges SQL Server lock data |
| GET | `/diff` | Compares two protocols; requires `scope`, `from`, `to` params |
| POST | `/insert-controle-protocolo` | Records a protocol lock with `NUM_PROTOCOLO` + `NME_USUARIO` |
| POST | `/delete-controle-protocolo` | Removes a protocol lock by `NUM_PROTOCOLO` |

## Production Deployment (Linux)

The service runs as a systemd unit at `/etc/systemd/system/rdsl_protocolo.service` on `/appapi/rdsl_protocolo/`. Use `systemctl restart rdsl_protocolo` to apply changes and `journalctl -u rdsl_protocolo -f` to tail logs.
