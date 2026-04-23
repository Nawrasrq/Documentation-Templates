"""Discover Confluence page tree and generate a docs_map.yml."""
from __future__ import annotations

import logging

from src.confluence_client import ConfluenceClient, PageNode
from src.config import Config
from src.docs_mapper import DocsMap, PageMapping

logger = logging.getLogger(__name__)


def discover_pages(
    cfg: Config,
    *,
    space_key: str | None = None,
    parent_id: str | None = None,
    output_path: str = "config/docs_map.yml",
) -> list[PageMapping]:
    """Scan a Confluence space or subtree and generate docs_map.yml.

    Uses the v2 API so that folders and their children are discovered.

    Parameters
    ----------
    cfg : Config
        Application configuration.
    space_key : str | None
        Confluence space key. Falls back to cfg.confluence_space_key.
    parent_id : str | None
        If given, only scan this page/folder and its descendants.
        If None, scans the full space.
    output_path : str
        Where to write the generated docs_map.yml.

    Returns
    -------
    list[PageMapping]
        The discovered page mappings.
    """
    client = ConfluenceClient(cfg)
    resolved_space = space_key or cfg.confluence_space_key

    if parent_id:
        logger.info("Scanning page tree under parent %s", parent_id)
        root = client.get_page_tree(parent_id)
        print_tree(root)
        mappings = _flatten_tree(root, parent_id_override=None)
    elif resolved_space:
        logger.info("Scanning space '%s' root pages", resolved_space)
        roots = client.get_space_root_pages(resolved_space)
        mappings: list[PageMapping] = []
        for root_node in roots:
            tree = client.get_page_tree(root_node.page_id)
            print_tree(tree)
            mappings.extend(_flatten_tree(tree, parent_id_override=None))
    else:
        logger.error("No space key or parent ID provided. Set CONFLUENCE_SPACE_KEY or use --parent-id.")
        return []

    # Deduplicate by page_id (keep first occurrence)
    seen: set[str] = set()
    unique: list[PageMapping] = []
    for m in mappings:
        if m.page_id not in seen:
            seen.add(m.page_id)
            unique.append(m)
    mappings = unique

    logger.info("Discovered %d unique page(s)/folder(s)", len(mappings))

    DocsMap.save(mappings, output_path)
    return mappings


def _flatten_tree(node: PageNode, parent_id_override: str | None) -> list[PageMapping]:
    """Recursively flatten a PageNode tree into PageMapping entries.

    Folders are included with a ``# folder`` comment in the pattern
    so you can visually distinguish them in the YAML.

    Parameters
    ----------
    node : PageNode
        Current tree node.
    parent_id_override : str | None
        Parent page ID to record. None for the root node.

    Returns
    -------
    list[PageMapping]
        Flat list of page mappings with hierarchy info.
    """
    slug = _slugify(node.title)
    is_folder = node.content_type == "folder"

    title_label = f"[folder] {node.title}" if is_folder else node.title

    mappings: list[PageMapping] = [
        PageMapping(
            pattern=f"**/{slug}/**",
            page_id=node.page_id,
            title=title_label,
            parent_id=parent_id_override or node.parent_id or None,
        )
    ]

    for child in node.children:
        mappings.extend(_flatten_tree(child, parent_id_override=node.page_id))

    return mappings


def print_tree(node: PageNode, indent: int = 0) -> None:
    """Print a PageNode tree to the logger for visual inspection.

    Parameters
    ----------
    node : PageNode
        Root of the tree to print.
    indent : int
        Current indentation level.
    """
    prefix = "    " * indent
    connector = "├── " if indent > 0 else ""
    type_tag = " [folder]" if node.content_type == "folder" else ""
    logger.info("%s%s%s [%s]%s", prefix, connector, node.title, node.page_id, type_tag)
    for child in node.children:
        print_tree(child, indent + 1)


def _slugify(title: str) -> str:
    """Convert a page title to a lowercase slug for use in glob patterns.

    Parameters
    ----------
    title : str
        Page title.

    Returns
    -------
    str
        Lowercased, hyphenated slug.
    """
    return title.lower().replace(" ", "-").replace("/", "-").strip("-")
