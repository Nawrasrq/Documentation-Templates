from __future__ import annotations

import logging
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PageMapping:
    """A single mapping from file-path pattern to a Confluence page.

    Attributes
    ----------
    pattern : str
        Glob pattern matched against changed file paths.
    page_id : str
        Confluence page ID.
    title : str
        Human-readable label.
    parent_id : str | None
        Parent page ID (preserves Confluence hierarchy).
    section : str | None
        Optional heading to scope updates to.
    """

    pattern: str
    page_id: str
    title: str
    parent_id: str | None = None
    section: str | None = None


@dataclass
class DocsMap:
    """Parsed docs_map.yml with match logic.

    Attributes
    ----------
    mappings : list[PageMapping]
        File-pattern to Confluence-page mappings.
    warn_on_no_match : bool
        Log a warning when no patterns match the changed files.
    """

    mappings: list[PageMapping]
    warn_on_no_match: bool = True

    # MARK: Load / Save

    @classmethod
    def load(cls, path: str | Path) -> DocsMap:
        """Load and parse a docs_map.yml file.

        Parameters
        ----------
        path : str | Path
            Path to the YAML file.

        Returns
        -------
        DocsMap
            Parsed docs map.
        """
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        mappings = [
            PageMapping(
                pattern=m["pattern"],
                page_id=str(m["page_id"]),
                title=m.get("title", ""),
                parent_id=m.get("parent_id"),
                section=m.get("section"),
            )
            for m in raw.get("mappings", [])
        ]
        return cls(
            mappings=mappings,
            warn_on_no_match=raw.get("warn_on_no_match", True),
        )

    @staticmethod
    def save(
        mappings: list[PageMapping],
        path: str | Path,
        *,
        warn_on_no_match: bool = True,
    ) -> None:
        """Write a list of PageMappings to a YAML file.

        Parameters
        ----------
        mappings : list[PageMapping]
            Mappings to serialize.
        path : str | Path
            Output file path.
        warn_on_no_match : bool
            Value for the warn_on_no_match flag.
        """
        data: dict = {
            "mappings": [
                {
                    k: v
                    for k, v in {
                        "page_id": m.page_id,
                        "title": m.title,
                        "parent_id": m.parent_id,
                        "pattern": m.pattern,
                        "section": m.section,
                    }.items()
                    if v is not None
                }
                for m in mappings
            ],
            "warn_on_no_match": warn_on_no_match,
        }

        with open(path, "w", encoding="utf-8") as fh:
            yaml.dump(data, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)

        logger.info("Wrote %d mapping(s) to %s", len(mappings), path)

    # MARK: Matching

    def match(self, changed_files: list[str]) -> list[PageMapping]:
        """Return de-duplicated page mappings that match any changed files.

        Parameters
        ----------
        changed_files : list[str]
            File paths to match against.

        Returns
        -------
        list[PageMapping]
            Matched mappings (de-duplicated by page_id + section).
        """
        matched: dict[str, PageMapping] = {}
        for filepath in changed_files:
            normalized = filepath.replace("\\", "/")
            for mapping in self.mappings:
                if fnmatch(normalized, mapping.pattern):
                    key = f"{mapping.page_id}:{mapping.section or ''}"
                    matched[key] = mapping
        return list(matched.values())
