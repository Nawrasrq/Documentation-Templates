"""Create or populate Confluence pages from markdown project summaries."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from src.claude_client import ClaudeClient
from src.confluence_client import ConfluenceClient
from src.config import VALID_TEMPLATE_TYPES, Config

logger = logging.getLogger(__name__)


@dataclass
class CreateResult:
    """Outcome of a page creation attempt.

    Attributes
    ----------
    page_id : str
        Confluence page ID (existing or newly created).
    page_title : str
        Title of the page.
    created : bool
        True if a new page was created (vs updating existing).
    error : str | None
        Error message if something failed.
    """

    page_id: str
    page_title: str
    created: bool
    error: str | None = None


def create_page(
    cfg: Config,
    *,
    source_path: str,
    template_type: str,
    page_id: str | None = None,
    page_title: str | None = None,
    space_key: str | None = None,
    parent_id: str | None = None,
    dry_run: bool = False,
) -> CreateResult:
    """Generate a Confluence page from a markdown summary file.

    Either ``page_id`` (to update an existing/skeleton page) or
    ``space_key`` (to create a new page) must be provided.

    Parameters
    ----------
    cfg : Config
        Application configuration.
    source_path : str
        Path to the markdown project summary.
    template_type : str
        Documentation template type (etl, api, sql_table, tool).
    page_id : str | None
        Existing Confluence page ID to populate.
    page_title : str | None
        Title for the page. If page_id is given and this is None,
        the existing page title is used.
    space_key : str | None
        Space key for creating a new page.
    parent_id : str | None
        Parent page ID when creating a new page.
    dry_run : bool
        If True, generate content but don't write to Confluence.

    Returns
    -------
    CreateResult
        Outcome of the operation.

    Raises
    ------
    ValueError
        If template_type is invalid or required arguments are missing.
    FileNotFoundError
        If source_path does not exist.
    """
    if template_type not in VALID_TEMPLATE_TYPES:
        raise ValueError(
            f"Invalid template type '{template_type}'. Must be one of: {VALID_TEMPLATE_TYPES}"
        )

    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Source markdown file not found: {source}")

    source_markdown = source.read_text(encoding="utf-8")
    logger.info("Read source: %s (%d chars)", source, len(source_markdown))

    confluence = ConfluenceClient(cfg)
    claude = ClaudeClient(cfg)

    # MARK: Populate Existing Page

    if page_id:
        return _populate_existing(
            confluence, claude,
            page_id=page_id,
            page_title=page_title,
            source_markdown=source_markdown,
            template_type=template_type,
            dry_run=dry_run,
        )

    # MARK: Create New Page

    resolved_space = space_key or cfg.confluence_space_key
    if not resolved_space:
        raise ValueError("No space key provided. Set CONFLUENCE_SPACE_KEY or use --space-key.")

    resolved_title = page_title or source.stem.replace("-", " ").replace("_", " ").title()

    return _create_new(
        confluence, claude,
        space_key=resolved_space,
        parent_id=parent_id,
        page_title=resolved_title,
        source_markdown=source_markdown,
        template_type=template_type,
        dry_run=dry_run,
    )


def _populate_existing(
    confluence: ConfluenceClient,
    claude: ClaudeClient,
    *,
    page_id: str,
    page_title: str | None,
    source_markdown: str,
    template_type: str,
    dry_run: bool,
) -> CreateResult:
    """Fill an existing (possibly skeleton) Confluence page."""
    try:
        page = confluence.get_page(page_id)
        title = page_title or page.title
        existing_body = page.body if page.body.strip() else None

        logger.info("Target page: '%s' [%s] (v%d)", page.title, page_id, page.version)

        generated_body = claude.generate_page(
            source_markdown=source_markdown,
            template_type=template_type,
            page_title=title,
            existing_body=existing_body,
        )

        if dry_run:
            logger.info("[DRY RUN] Would write %d chars to '%s'", len(generated_body), title)
        else:
            confluence.update_page(page_id, title, generated_body, page.version)

        return CreateResult(page_id=page_id, page_title=title, created=False)

    except Exception as exc:
        logger.exception("Failed to populate page %s", page_id)
        return CreateResult(
            page_id=page_id or "", page_title=page_title or "",
            created=False, error=str(exc),
        )


def _create_new(
    confluence: ConfluenceClient,
    claude: ClaudeClient,
    *,
    space_key: str,
    parent_id: str | None,
    page_title: str,
    source_markdown: str,
    template_type: str,
    dry_run: bool,
) -> CreateResult:
    """Create a brand-new Confluence page."""
    try:
        generated_body = claude.generate_page(
            source_markdown=source_markdown,
            template_type=template_type,
            page_title=page_title,
        )

        if dry_run:
            logger.info(
                "[DRY RUN] Would create page '%s' in space %s (%d chars)",
                page_title, space_key, len(generated_body),
            )
            return CreateResult(page_id="(dry-run)", page_title=page_title, created=True)

        result = confluence.create_page(
            space_key=space_key,
            title=page_title,
            body=generated_body,
            parent_id=parent_id,
        )
        new_id = str(result["id"])
        return CreateResult(page_id=new_id, page_title=page_title, created=True)

    except Exception as exc:
        logger.exception("Failed to create page '%s'", page_title)
        return CreateResult(
            page_id="", page_title=page_title, created=False, error=str(exc),
        )
