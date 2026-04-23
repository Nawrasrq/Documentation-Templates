from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
VALID_TEMPLATE_TYPES = ("etl", "api", "sql_table", "tool")


@dataclass(frozen=True)
class Config:
    """Central configuration populated from environment variables.

    Attributes
    ----------
    anthropic_api_key : str
        Anthropic API key for Claude calls.
    claude_model : str
        Claude model identifier.
    confluence_base_url : str
        Atlassian Cloud wiki base URL.
    confluence_user_email : str
        Atlassian account email for basic-auth.
    confluence_token : str
        Confluence API token.
    confluence_space_key : str
        Default Confluence space key (used by discover command).
    docs_map_path : str
        Path to the docs_map.yml file.
    templates_dir : str
        Path to the documentation templates directory.
    """

    # Anthropic
    anthropic_api_key: str = field(repr=False, default="")
    claude_model: str = "claude-sonnet-4-6"

    # Confluence (Atlassian Cloud)
    confluence_base_url: str = ""
    confluence_user_email: str = ""
    confluence_token: str = field(repr=False, default="")
    confluence_space_key: str = ""

    # Paths
    docs_map_path: str = "config/docs_map.yml"
    templates_dir: str = str(TEMPLATES_DIR)

    # MARK: Factory

    @classmethod
    def from_env(cls) -> Config:
        """Build a Config instance from environment variables."""
        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            claude_model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
            confluence_base_url=os.environ.get("CONFLUENCE_BASE_URL", "").rstrip("/"),
            confluence_user_email=os.environ.get("CONFLUENCE_USER_EMAIL", ""),
            confluence_token=os.environ.get("CONFLUENCE_TOKEN", ""),
            confluence_space_key=os.environ.get("CONFLUENCE_SPACE_KEY", ""),
            docs_map_path=os.environ.get("DOCS_MAP_PATH", "config/docs_map.yml"),
            templates_dir=os.environ.get("TEMPLATES_DIR", str(TEMPLATES_DIR)),
        )

    # MARK: Validation

    def validate(self, needs_confluence: bool = True, needs_claude: bool = True) -> list[str]:
        """Return a list of missing-but-required config fields.

        Parameters
        ----------
        needs_confluence : bool
            Whether Confluence credentials are required.
        needs_claude : bool
            Whether the Anthropic API key is required.

        Returns
        -------
        list[str]
            Names of missing environment variables.
        """
        missing: list[str] = []

        if needs_claude and not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")

        if needs_confluence:
            if not self.confluence_base_url:
                missing.append("CONFLUENCE_BASE_URL")
            if not self.confluence_user_email:
                missing.append("CONFLUENCE_USER_EMAIL")
            if not self.confluence_token:
                missing.append("CONFLUENCE_TOKEN")

        return missing
