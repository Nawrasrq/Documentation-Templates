from __future__ import annotations

import logging
from dataclasses import dataclass
from fnmatch import fnmatch

from src.claude_client import ClaudeClient
from src.confluence_client import ConfluenceClient
from src.config import Config
from src.docs_mapper import DocsMap, PageMapping
from src.git_client import ChangeSet

logger = logging.getLogger(__name__)


@dataclass
class UpdateResult:
    """Outcome of processing a single page mapping.

    Attributes
    ----------
    page_id : str
        Confluence page ID.
    page_title : str
        Page title.
    section : str | None
        Targeted section heading, if any.
    changed : bool
        Whether the page was updated.
    error : str | None
        Error message if processing failed.
    """

    page_id: str
    page_title: str
    section: str | None
    changed: bool
    error: str | None = None


class UpdatePipeline:
    """Orchestrate git-diff-based Confluence page updates.

    Parameters
    ----------
    cfg : Config
        Application configuration.
    docs_map : DocsMap
        File-pattern-to-page mappings.
    """

    def __init__(self, cfg: Config, docs_map: DocsMap) -> None:
        self.docs_map = docs_map
        self.confluence = ConfluenceClient(cfg)
        self.claude = ClaudeClient(cfg)

    # MARK: Run

    def run(self, changeset: ChangeSet, *, dry_run: bool = False) -> list[UpdateResult]:
        """Execute the update pipeline for a set of code changes.

        Parameters
        ----------
        changeset : ChangeSet
            Git changes to process.
        dry_run : bool
            If True, skip writing to Confluence.

        Returns
        -------
        list[UpdateResult]
            One result per matched page mapping.
        """
        logger.info("Changes: %s", changeset.summary)
        logger.info("Files changed: %s", ", ".join(changeset.changed_files) or "(none)")

        if not changeset.changed_files:
            logger.info("No changed files — nothing to do.")
            return []

        matched = self.docs_map.match(changeset.changed_files)
        if not matched:
            msg = "No docs-map entries matched the changed files."
            if self.docs_map.warn_on_no_match:
                logger.warning(msg)
            else:
                logger.info(msg)
            return []

        logger.info("Matched %d page mapping(s): %s", len(matched), [m.title for m in matched])

        results: list[UpdateResult] = []
        for mapping in matched:
            result = self._process_mapping(mapping, changeset, dry_run=dry_run)
            results.append(result)

        return results

    # MARK: Processing

    def _process_mapping(
        self, mapping: PageMapping, changeset: ChangeSet, *, dry_run: bool
    ) -> UpdateResult:
        """Fetch page, call Claude, and optionally write the update."""
        try:
            relevant_diff = self._collect_relevant_diff(mapping, changeset)
            if not relevant_diff:
                logger.info("No diff content for mapping '%s' — skipping.", mapping.title)
                return UpdateResult(
                    page_id=mapping.page_id, page_title=mapping.title,
                    section=mapping.section, changed=False,
                )

            page = self.confluence.get_page(mapping.page_id)
            logger.info(
                "Fetched page '%s' (v%d, %d chars)", page.title, page.version, len(page.body),
            )

            updated_body = self.claude.generate_update(
                diff=relevant_diff,
                commit_message=changeset.summary,
                page_body=page.body,
                page_title=page.title,
                section=mapping.section,
            )

            changed = updated_body.strip() != page.body.strip()
            if not changed:
                logger.info("Claude returned unchanged content for '%s' — skipping write.", page.title)
                return UpdateResult(
                    page_id=mapping.page_id, page_title=page.title,
                    section=mapping.section, changed=False,
                )

            if dry_run:
                logger.info(
                    "[DRY RUN] Would update '%s' (%d -> %d chars)",
                    page.title, len(page.body), len(updated_body),
                )
            else:
                self.confluence.update_page(
                    page.page_id, page.title, updated_body, page.version,
                )

            return UpdateResult(
                page_id=mapping.page_id, page_title=page.title,
                section=mapping.section, changed=True,
            )

        except Exception as exc:
            logger.exception("Error processing mapping '%s'", mapping.title)
            return UpdateResult(
                page_id=mapping.page_id, page_title=mapping.title,
                section=mapping.section, changed=False, error=str(exc),
            )

    @staticmethod
    def _collect_relevant_diff(mapping: PageMapping, changeset: ChangeSet) -> str:
        """Concatenate diffs for files matching this mapping's pattern."""
        parts: list[str] = []
        for filepath, diff_text in changeset.diffs.items():
            if fnmatch(filepath.replace("\\", "/"), mapping.pattern):
                parts.append(diff_text)
        return "\n".join(parts)
