"""Publish markdown files directly to Confluence without Claude."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import markdown

from src.confluence_client import ConfluenceClient
from src.config import Config

logger = logging.getLogger(__name__)


@dataclass
class PublishResult:
    """Outcome of a publish operation.

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


# MARK: Public API

def publish_page(
    cfg: Config,
    *,
    source_path: str,
    page_id: str | None = None,
    page_title: str | None = None,
    space_key: str | None = None,
    parent_id: str | None = None,
    dry_run: bool = False,
) -> PublishResult:
    """Convert a markdown file to Confluence storage format and publish it.

    Either ``page_id`` (to update an existing page) or ``space_key``
    (to create a new page) must be provided.

    Parameters
    ----------
    cfg : Config
        Application configuration.
    source_path : str
        Path to the markdown file.
    page_id : str | None
        Existing Confluence page ID to overwrite.
    page_title : str | None
        Page title. Defaults to existing title or the markdown H1 / filename.
    space_key : str | None
        Space key for creating a new page.
    parent_id : str | None
        Parent page/folder ID when creating under a specific location.
    dry_run : bool
        If True, convert but don't write to Confluence.

    Returns
    -------
    PublishResult
        Outcome of the operation.

    Raises
    ------
    FileNotFoundError
        If source_path does not exist.
    ValueError
        If neither page_id nor space_key is provided.
    """
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Source markdown file not found: {source}")

    md_text = source.read_text(encoding="utf-8")
    logger.info("Read source: %s (%d chars)", source, len(md_text))

    body = md_to_confluence(md_text)
    logger.info("Converted to Confluence storage format (%d chars)", len(body))

    resolved_title = page_title or _extract_title(md_text, source)

    confluence = ConfluenceClient(cfg)

    if page_id:
        return _update_existing(confluence, page_id=page_id, title=resolved_title,
                                body=body, dry_run=dry_run)

    resolved_space = space_key or cfg.confluence_space_key
    if not resolved_space:
        raise ValueError("No space key provided. Set CONFLUENCE_SPACE_KEY or use --space-key.")

    return _create_new(confluence, space_key=resolved_space, parent_id=parent_id,
                       title=resolved_title, body=body, dry_run=dry_run)


# MARK: Markdown → Confluence

_CODE_BLOCK_RE = re.compile(
    r'<pre><code\s+class="language-(\w+)">(.*?)</code></pre>',
    re.DOTALL,
)
_CODE_BLOCK_PLAIN_RE = re.compile(
    r"<pre><code>(.*?)</code></pre>",
    re.DOTALL,
)


def md_to_confluence(md_text: str) -> str:
    """Convert markdown text to Confluence storage-format XHTML.

    Handles fenced code blocks by converting them to Confluence
    ``code`` structured macros for proper syntax highlighting.

    Parameters
    ----------
    md_text : str
        Raw markdown content.

    Returns
    -------
    str
        Confluence storage-format XHTML body.
    """
    html = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "toc", "attr_list", "md_in_html"],
        output_format="html",
    )

    html = _CODE_BLOCK_RE.sub(_replace_code_block_with_lang, html)
    html = _CODE_BLOCK_PLAIN_RE.sub(_replace_code_block_plain, html)

    return html


def _replace_code_block_with_lang(match: re.Match[str]) -> str:
    """Replace a fenced code block with a Confluence code macro."""
    lang = match.group(1)
    code = _unescape_html(match.group(2))
    return (
        f'<ac:structured-macro ac:name="code">'
        f'<ac:parameter ac:name="language">{lang}</ac:parameter>'
        f"<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>"
        f"</ac:structured-macro>"
    )


def _replace_code_block_plain(match: re.Match[str]) -> str:
    """Replace a plain code block (no language) with a Confluence code macro."""
    code = _unescape_html(match.group(1))
    return (
        f'<ac:structured-macro ac:name="code">'
        f"<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>"
        f"</ac:structured-macro>"
    )


def _unescape_html(text: str) -> str:
    """Reverse HTML entity escaping that the markdown library applies inside code blocks."""
    return (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#x27;", "'")
    )


def _extract_title(md_text: str, source: Path) -> str:
    """Pull a page title from the first H1 heading, or fall back to the filename.

    Parameters
    ----------
    md_text : str
        Raw markdown content.
    source : Path
        Source file path (used as fallback).

    Returns
    -------
    str
        Extracted or generated title.
    """
    for line in md_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped.lstrip("# ").strip()

    return source.stem.replace("-", " ").replace("_", " ").title()


# MARK: Confluence Operations

def _update_existing(
    confluence: ConfluenceClient,
    *,
    page_id: str,
    title: str,
    body: str,
    dry_run: bool,
) -> PublishResult:
    """Overwrite an existing Confluence page with converted markdown."""
    try:
        page = confluence.get_page(page_id)
        final_title = title or page.title

        logger.info("Target page: '%s' [%s] (v%d)", page.title, page_id, page.version)

        if dry_run:
            logger.info("[DRY RUN] Would write %d chars to '%s'", len(body), final_title)
        else:
            confluence.update_page(page_id, final_title, body, page.version)

        return PublishResult(page_id=page_id, page_title=final_title, created=False)

    except Exception as exc:
        logger.exception("Failed to publish to page %s", page_id)
        return PublishResult(
            page_id=page_id, page_title=title, created=False, error=str(exc),
        )


def _create_new(
    confluence: ConfluenceClient,
    *,
    space_key: str,
    parent_id: str | None,
    title: str,
    body: str,
    dry_run: bool,
) -> PublishResult:
    """Create a brand-new Confluence page from converted markdown."""
    try:
        if dry_run:
            logger.info(
                "[DRY RUN] Would create page '%s' in space %s (%d chars)",
                title, space_key, len(body),
            )
            return PublishResult(page_id="(dry-run)", page_title=title, created=True)

        result = confluence.create_page(
            space_key=space_key,
            title=title,
            body=body,
            parent_id=parent_id,
        )
        new_id = str(result["id"])
        return PublishResult(page_id=new_id, page_title=title, created=True)

    except Exception as exc:
        logger.exception("Failed to create page '%s'", title)
        return PublishResult(page_id="", page_title=title, created=False, error=str(exc))
