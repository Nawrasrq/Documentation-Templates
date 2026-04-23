"""Shared pytest fixtures for documentation-automation tests."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml


# MARK: Docs Map Fixtures

@pytest.fixture
def sample_docs_map_path(tmp_path: Path) -> Path:
    """Create a sample docs_map.yml in a temp directory.

    Returns
    -------
    Path
        Path to the temporary docs_map.yml file.
    """
    data = {
        "mappings": [
            {"pattern": "src/etl/*.py", "page_id": "111", "title": "ETL Overview"},
            {"pattern": "config/*.yml", "page_id": "222", "title": "Config Guide", "section": "Reference"},
            {"pattern": "docs/**", "page_id": "333", "title": "Dev Guide"},
        ],
        "warn_on_no_match": True,
    }
    path = tmp_path / "docs_map.yml"
    path.write_text(yaml.dump(data), encoding="utf-8")
    return path


# MARK: Markdown Fixtures

@pytest.fixture
def sample_markdown(tmp_path: Path) -> Path:
    """Create a sample markdown project summary.

    Returns
    -------
    Path
        Path to the temporary markdown file.
    """
    content = """\
# My ETL Process

This ETL extracts data from the sales database, transforms it, and loads
it into the analytics warehouse.

## Tech Stack
- Python 3.11
- pandas, sqlalchemy

## How to Run
```bash
python main/main.py
```

## Scheduling
Runs nightly at 2:00 AM via Windows Task Scheduler.
"""
    path = tmp_path / "my-etl.md"
    path.write_text(content, encoding="utf-8")
    return path


# MARK: Template Fixtures

@pytest.fixture
def templates_dir(tmp_path: Path) -> Path:
    """Create a minimal templates directory.

    Returns
    -------
    Path
        Path to the temporary templates directory.
    """
    tpl_dir = tmp_path / "templates"
    tpl_dir.mkdir()

    (tpl_dir / "writing_standards.md").write_text("Write clearly.\n", encoding="utf-8")
    (tpl_dir / "etl.md").write_text("ETL template placeholder.\n", encoding="utf-8")
    (tpl_dir / "api.md").write_text("API template placeholder.\n", encoding="utf-8")
    (tpl_dir / "sql_table.md").write_text("SQL template placeholder.\n", encoding="utf-8")
    (tpl_dir / "tool.md").write_text("Tool template placeholder.\n", encoding="utf-8")

    return tpl_dir


# MARK: Mock Clients

@pytest.fixture
def mock_confluence_client() -> Mock:
    """Create a mock ConfluenceClient.

    Returns
    -------
    Mock
        Mock with get_page, update_page, and create_page stubs.
    """
    client = Mock()
    client.get_page.return_value = Mock(
        page_id="111",
        title="Test Page",
        version=5,
        body="<p>Existing content</p>",
        space_key="TEST",
        parent_id="",
    )
    client.update_page.return_value = {"id": "111"}
    client.create_page.return_value = {"id": "999"}
    return client


@pytest.fixture
def mock_claude_client() -> Mock:
    """Create a mock ClaudeClient.

    Returns
    -------
    Mock
        Mock with generate_update and generate_page stubs.
    """
    client = Mock()
    client.generate_update.return_value = "<p>Updated content</p>"
    client.generate_page.return_value = "<p>Generated page</p>"
    return client


# MARK: Temp Directory

@pytest.fixture
def temp_directory() -> Path:
    """Create a temporary directory that is cleaned up after the test.

    Yields
    ------
    Path
        Path to the temporary directory.
    """
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


# MARK: Environment Setup

@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set safe test environment variables.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture.
    """
    test_env = {
        "ANTHROPIC_API_KEY": "test-key",
        "CONFLUENCE_BASE_URL": "https://test.atlassian.net/wiki",
        "CONFLUENCE_USER_EMAIL": "test@test.com",
        "CONFLUENCE_TOKEN": "test-token",
        "CONFLUENCE_SPACE_KEY": "TEST",
        "CLAUDE_MODEL": "claude-sonnet-4-6",
    }
    for key, value in test_env.items():
        monkeypatch.setenv(key, value)
