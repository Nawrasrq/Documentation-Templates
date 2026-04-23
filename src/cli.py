"""CLI entry point with subcommands: update, create, discover.

Usage:
    python -m src.cli update                          # update from last commit
    python -m src.cli create -s docs/my-etl.md -t etl --page-id 123
    python -m src.cli discover --space-key ENG
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.config import VALID_TEMPLATE_TYPES, Config
from src.pipeline import UpdateResult

LOG_FILE = Path("logs/doc-automation.log")


def _add_common_args(p: argparse.ArgumentParser) -> None:
    """Add flags shared by all subcommands."""
    p.add_argument("--verbose", "-v", action="store_true", help="Enable debug-level logging.")


def _setup_logging(verbose: bool) -> None:
    """Configure logging to both console and a log file (overwritten each run)."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"

    root = logging.getLogger()
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(fmt))
    root.addHandler(console)

    file_handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(fmt))
    root.addHandler(file_handler)

    logging.debug("Logging to %s", LOG_FILE.resolve())


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the appropriate subcommand."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="doc-automation",
        description="Confluence documentation automation — update, create, and discover pages.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    _build_update_parser(subparsers)
    _build_create_parser(subparsers)
    _build_discover_parser(subparsers)

    args = parser.parse_args(argv)

    _setup_logging(args.verbose)

    handlers = {
        "update": _handle_update,
        "create": _handle_create,
        "discover": _handle_discover,
    }
    return handlers[args.command](args)


# MARK: Update Subcommand

def _build_update_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser("update", help="Update Confluence pages from git changes.")
    _add_common_args(p)

    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--last", type=int, default=None, metavar="N",
                       help="Check the last N commits (default: 1).")
    mode.add_argument("--uncommitted", action="store_true",
                       help="Check uncommitted (staged + unstaged) changes.")
    mode.add_argument("--commit", default=None, metavar="HASH",
                       help="Check a specific commit hash.")
    mode.add_argument("--branch", default=None, metavar="BASE",
                       help="Check all changes on current branch vs BASE.")

    p.add_argument("--dry-run", action="store_true",
                    help="Show what would be updated without writing to Confluence.")
    p.add_argument("--docs-map", default=None,
                    help="Path to docs_map.yml (overrides DOCS_MAP_PATH env var).")
    p.add_argument("--repo-dir", default=".",
                    help="Path to the git repository (default: current directory).")


def _handle_update(args: argparse.Namespace) -> int:
    from src.docs_mapper import DocsMap
    from src.git_client import GitClient
    from src.pipeline import UpdatePipeline

    cfg = Config.from_env()
    missing = cfg.validate(needs_confluence=True, needs_claude=True)
    if missing:
        logging.error("Missing required environment variables: %s", ", ".join(missing))
        return 1

    docs_map_path = args.docs_map or cfg.docs_map_path
    try:
        docs_map = DocsMap.load(docs_map_path)
    except FileNotFoundError:
        logging.error("docs_map file not found: %s", docs_map_path)
        return 1

    logging.info("Loaded %d mapping(s) from %s", len(docs_map.mappings), docs_map_path)

    git = GitClient(repo_dir=args.repo_dir)

    if args.uncommitted:
        changeset = git.get_uncommitted()
    elif args.commit:
        changeset = git.get_commit(args.commit)
    elif args.branch:
        changeset = git.get_branch_diff(args.branch)
    else:
        changeset = git.get_last_commits(args.last or 1)

    logging.info("%s", changeset.summary)
    if not changeset.changed_files:
        logging.info("No changes detected — nothing to do.")
        return 0

    pipeline = UpdatePipeline(cfg, docs_map)
    results = pipeline.run(changeset, dry_run=args.dry_run)

    return _report_results(results)


# MARK: Create Subcommand

def _build_create_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        "create", help="Create/populate a Confluence page from a markdown summary.",
    )
    _add_common_args(p)
    p.add_argument("-s", "--source", required=True,
                    help="Path to the markdown project summary file.")
    p.add_argument("-t", "--template", required=True, choices=VALID_TEMPLATE_TYPES,
                    help="Documentation template type.")
    p.add_argument("--page-id", default=None,
                    help="Existing Confluence page ID to populate (for skeleton pages).")
    p.add_argument("--page-title", default=None,
                    help="Page title (defaults to existing title or source filename).")
    p.add_argument("--space-key", default=None,
                    help="Confluence space key (for creating new pages).")
    p.add_argument("--parent-id", default=None,
                    help="Parent page ID (for creating new pages under a specific page).")
    p.add_argument("--dry-run", action="store_true",
                    help="Generate content but don't write to Confluence.")


def _handle_create(args: argparse.Namespace) -> int:
    from src.create import create_page

    cfg = Config.from_env()
    missing = cfg.validate(needs_confluence=not args.dry_run, needs_claude=True)
    if missing:
        logging.error("Missing required environment variables: %s", ", ".join(missing))
        return 1

    if not args.page_id and not (args.space_key or cfg.confluence_space_key):
        logging.error("Provide --page-id (to populate existing) or --space-key (to create new).")
        return 1

    try:
        result = create_page(
            cfg,
            source_path=args.source,
            template_type=args.template,
            page_id=args.page_id,
            page_title=args.page_title,
            space_key=args.space_key,
            parent_id=args.parent_id,
            dry_run=args.dry_run,
        )
    except (ValueError, FileNotFoundError) as exc:
        logging.error("%s", exc)
        return 1

    if result.error:
        logging.error("Failed: %s — %s", result.page_title, result.error)
        return 1

    action = "Created" if result.created else "Populated"
    logging.info("%s: %s [%s]", action, result.page_title, result.page_id)
    return 0


# MARK: Discover Subcommand

def _build_discover_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        "discover", help="Scan Confluence and generate docs_map.yml.",
    )
    _add_common_args(p)
    p.add_argument("--space-key", default=None,
                    help="Confluence space key to scan.")
    p.add_argument("--parent-id", default=None,
                    help="Scan only under this page ID (instead of full space).")
    p.add_argument("-o", "--output", default="config/docs_map.yml",
                    help="Output path for generated docs_map.yml (default: config/docs_map.yml).")


def _handle_discover(args: argparse.Namespace) -> int:
    from src.discover import discover_pages

    cfg = Config.from_env()
    missing = cfg.validate(needs_confluence=True, needs_claude=False)
    if missing:
        logging.error("Missing required environment variables: %s", ", ".join(missing))
        return 1

    if not args.space_key and not args.parent_id and not cfg.confluence_space_key:
        logging.error("Provide --space-key or --parent-id, or set CONFLUENCE_SPACE_KEY.")
        return 1

    mappings = discover_pages(
        cfg,
        space_key=args.space_key,
        parent_id=args.parent_id,
        output_path=args.output,
    )

    if not mappings:
        logging.warning("No pages discovered.")
        return 1

    logging.info("Discovered %d page(s) — written to %s", len(mappings), args.output)
    return 0


# MARK: Reporting

def _report_results(results: list[UpdateResult]) -> int:
    """Log a summary of update results and return exit code."""
    if not results:
        logging.info("No documentation pages matched — nothing to do.")
        return 0

    errors = [r for r in results if r.error]
    updated = [r for r in results if r.changed and not r.error]
    skipped = [r for r in results if not r.changed and not r.error]

    for r in updated:
        logging.info("  Updated: %s (page %s)", r.page_title, r.page_id)
    for r in skipped:
        logging.info("  Skipped: %s (no relevant changes)", r.page_title)
    for r in errors:
        logging.error("  Error:   %s — %s", r.page_title, r.error)

    logging.info("Done: %d updated, %d skipped, %d errors.", len(updated), len(skipped), len(errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
