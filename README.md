# Documentation Automation

Manage Confluence documentation from the command line — update pages from git changes, create pages from markdown summaries, publish markdown directly, and discover your Confluence page tree.

## Four Commands

```
update   →  git diff → match files → Claude → surgical Confluence update
create   →  markdown file + template → Claude → full Confluence page
publish  →  markdown file → Confluence page (no Claude needed)
discover →  scan Confluence space → generate docs_map.yml
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill in secrets
cp .env.example .env

# 3. Discover your Confluence pages (generates config/docs_map.yml)
python -m src.cli discover --space-key ENG

# 4. Publish a markdown file directly to Confluence
python -m src.cli publish -s docs/my-etl.md --parent-id 525664257 --dry-run

# 5. Create a page from a markdown summary (uses Claude for formatting)
python -m src.cli create -s docs/my-etl.md -t etl --page-id 123456789 --dry-run

# 6. Update pages from git changes
python -m src.cli update --dry-run
```

## Commands

### `update` — Sync docs with code changes

Detects local git changes, matches them to Confluence pages via `config/docs_map.yml`, and uses Claude to surgically update only the relevant sections.

```bash
python -m src.cli update                         # last commit (default)
python -m src.cli update --last 3                # last 3 commits
python -m src.cli update --uncommitted           # staged + unstaged changes
python -m src.cli update --commit abc123         # specific commit
python -m src.cli update --branch main           # current branch vs main
python -m src.cli update --dry-run --verbose     # preview without writing
```

### `create` — Build pages from markdown

Takes a markdown project summary and a documentation template, then generates a properly structured Confluence page.

```bash
# Populate an existing skeleton page
python -m src.cli create -s docs/my-etl.md -t etl --page-id 123456789

# Create a brand-new page in a space
python -m src.cli create -s docs/my-api.md -t api --space-key ENG --parent-id 987654321

# Preview without writing
python -m src.cli create -s docs/my-etl.md -t etl --page-id 123456789 --dry-run
```

**Template types:** `etl`, `api`, `sql_table`, `tool`

### `publish` — Post markdown directly to Confluence

Converts a markdown file to Confluence storage format and publishes it — no Claude API needed.

```bash
# Publish to an existing page (overwrites content)
python -m src.cli publish -s docs/health-monitor-etl-tools.md --page-id 123456789

# Create a new page under a parent folder
python -m src.cli publish -s docs/health-monitor-etl-tools.md --parent-id 525664257

# Preview the conversion without writing
python -m src.cli publish -s docs/health-monitor-etl-tools.md --parent-id 525664257 --dry-run
```

Handles headings, tables, code blocks (with syntax highlighting), lists, bold/italic, and links. Code fences are converted to Confluence `code` macros automatically.

### `discover` — Map your Confluence space

Walks a Confluence space or page tree and generates `config/docs_map.yml` with all page IDs.

```bash
# Scan an entire space
python -m src.cli discover --space-key ENG

# Scan under a specific parent page
python -m src.cli discover --parent-id 123456789

# Write to a custom path
python -m src.cli discover --space-key ENG -o config/my_map.yml
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | For create/update | Anthropic API key |
| `CLAUDE_MODEL` | No | Model name (default: `claude-sonnet-4-6`) |
| `CONFLUENCE_BASE_URL` | Yes | e.g. `https://yoursite.atlassian.net/wiki` |
| `CONFLUENCE_USER_EMAIL` | Yes | Atlassian account email |
| `CONFLUENCE_TOKEN` | Yes | Confluence API token |
| `CONFLUENCE_SPACE_KEY` | No | Default space key for discover/create |
| `DOCS_MAP_PATH` | No | Path to docs map (default: `config/docs_map.yml`) |
| `TEMPLATES_DIR` | No | Path to templates (default: `templates/`) |

### `config/docs_map.yml`

Maps file-path glob patterns to Confluence page IDs (used by the `update` command):

```yaml
mappings:
  - pattern: "src/etl/*.py"
    page_id: "123456789"
    title: "ETL Pipeline Overview"

  - pattern: "config/*.yml"
    page_id: "123456793"
    title: "Configuration Guide"
    section: "Configuration Reference"
```

Generate this file automatically with `python -m src.cli discover`, then edit the patterns to match your repo structure.

### Documentation Templates

The `templates/` directory contains Confluence page templates (from your Documentation-Templates repo) and writing standards:

| File | Purpose |
|---|---|
| `writing_standards.md` | Writing guidelines applied to all Claude output |
| `etl.md` | ETL / automated process page structure |
| `api.md` | REST API page structure |
| `sql_table.md` | Database table page structure |
| `tool.md` | Tool / manual process page structure |

### Markdown Summaries

Put your project markdown files in `docs/`. These are the source material for the `create` and `publish` commands:

```
docs/
├── sales-etl.md
├── inventory-api.md
└── users-table.md
```

## Project Structure

```
documentation-automation/
├── .vscode/                  # VS Code settings (Ruff, pytest, Pylance)
├── config/
│   └── docs_map.yml          # File-pattern → page-ID mappings
├── docs/                     # Markdown project summaries (input for create)
├── templates/                # Confluence page templates + writing standards
│   ├── writing_standards.md
│   ├── etl.md
│   ├── api.md
│   ├── sql_table.md
│   └── tool.md
├── src/
│   ├── cli.py                # CLI with subcommands (update, create, publish, discover)
│   ├── pipeline.py           # Update pipeline orchestration
│   ├── create.py             # Create pipeline (markdown + template → Claude → Confluence)
│   ├── publish.py            # Publish pipeline (markdown → Confluence, no Claude)
│   ├── discover.py           # Discover pipeline (Confluence → docs_map.yml)
│   ├── git_client.py         # Local git (subprocess) for change detection
│   ├── confluence_client.py  # Confluence REST API client
│   ├── claude_client.py      # Claude API client with template loading
│   ├── docs_mapper.py        # docs_map.yml parser + glob matching
│   └── config.py             # Environment variable configuration
├── tests/
│   └── conftest.py           # Shared fixtures
├── pyproject.toml            # Ruff, mypy, pytest config
├── requirements.txt
└── .env.example
```
