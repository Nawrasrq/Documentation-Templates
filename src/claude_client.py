from __future__ import annotations

import logging
from pathlib import Path

import anthropic

from src.config import Config

logger = logging.getLogger(__name__)

# MARK: System Prompts

UPDATE_SYSTEM_PROMPT = """\
You are a technical documentation assistant. Your job is to update Confluence \
wiki pages (in Confluence storage format — XHTML) so they stay in sync with \
code changes.

RULES:
1. You receive the unified diff of a code change, a summary of the changes, \
   and the current Confluence page content in storage format.
2. Produce ONLY the updated Confluence storage-format body. Do NOT wrap it in \
   markdown fences or add any commentary.
3. Make **surgical edits** — change only the parts of the page that relate to \
   the code diff. Preserve all other content, formatting, macros, and structure \
   exactly as-is.
4. If a section heading is provided, limit your edits to that section.
5. If the diff does not warrant any documentation change, return the page \
   content unchanged and nothing else.
6. Keep the same tone, tense, and terminology already used on the page.

{writing_standards}
"""

CREATE_SYSTEM_PROMPT = """\
You are a technical documentation assistant. Your job is to create Confluence \
wiki pages (in Confluence storage format — XHTML) from project summaries and \
source material.

RULES:
1. You receive a markdown project summary, a documentation template that \
   defines the required page structure, and optionally existing page content.
2. Produce ONLY the Confluence storage-format body. Do NOT wrap it in \
   markdown fences or add any commentary.
3. Follow the template structure exactly — every section in the template \
   must appear in the output. If information for a section is not available \
   in the source material, mark it with [NEEDS REVIEW] rather than guessing.
4. Mark sections as "N/A" rather than omitting them, so the reader knows \
   they were considered.
5. If existing page content is provided, merge the new information into it \
   rather than replacing it wholesale. Preserve any content that is still \
   accurate.
6. Use proper Confluence storage format: <h1>, <h2>, <h3> for headings, \
   <table> for tables, <ac:structured-macro> for macros, etc.
7. Always include a Last Verified Date in the Project Information section.
8. Always include a Related Pages section, even if empty.

{writing_standards}

TEMPLATE TO FOLLOW:
{template}
"""


def _load_text_file(path: Path) -> str:
    """Read a text file and return its contents.

    Parameters
    ----------
    path : Path
        Path to the text file.

    Returns
    -------
    str
        File contents.
    """
    return path.read_text(encoding="utf-8")


class ClaudeClient:
    """Client for the Anthropic Claude API.

    Parameters
    ----------
    cfg : Config
        Application configuration with the Anthropic API key.
    """

    def __init__(self, cfg: Config) -> None:
        self._client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
        self._model = cfg.claude_model
        self._templates_dir = Path(cfg.templates_dir)

    # MARK: Template Loading

    def _load_writing_standards(self) -> str:
        """Load the writing standards markdown file."""
        path = self._templates_dir / "writing_standards.md"
        if path.exists():
            return _load_text_file(path)
        logger.warning("Writing standards file not found: %s", path)
        return ""

    def _load_template(self, template_type: str) -> str:
        """Load a documentation template by type.

        Parameters
        ----------
        template_type : str
            One of: etl, api, sql_table, tool.

        Returns
        -------
        str
            Template file contents.

        Raises
        ------
        FileNotFoundError
            If the template file does not exist.
        """
        path = self._templates_dir / f"{template_type}.md"
        if not path.exists():
            raise FileNotFoundError(f"Template not found: {path}")
        return _load_text_file(path)

    # MARK: Update Mode

    def generate_update(
        self,
        diff: str,
        commit_message: str,
        page_body: str,
        page_title: str,
        section: str | None = None,
    ) -> str:
        """Generate a surgical update to a Confluence page from a code diff.

        Parameters
        ----------
        diff : str
            Unified diff text.
        commit_message : str
            Summary of what changed.
        page_body : str
            Current Confluence storage-format XHTML.
        page_title : str
            Title of the target page.
        section : str | None
            If set, limit edits to this heading.

        Returns
        -------
        str
            Updated Confluence storage-format body.
        """
        writing_standards = self._load_writing_standards()
        system = UPDATE_SYSTEM_PROMPT.format(writing_standards=writing_standards)

        parts = [
            f"## Change summary\n{commit_message}",
            f"## Diff\n```\n{diff}\n```",
            f'## Current Confluence page: "{page_title}"\n```xml\n{page_body}\n```',
        ]
        if section:
            parts.append(f'## Target section\nLimit your edits to the section titled "{section}".')

        user_msg = "\n\n".join(parts)
        return self._call(system, user_msg, context_label=f"update '{page_title}'")

    # MARK: Create Mode

    def generate_page(
        self,
        source_markdown: str,
        template_type: str,
        page_title: str,
        existing_body: str | None = None,
    ) -> str:
        """Generate a full Confluence page from a markdown summary and template.

        Parameters
        ----------
        source_markdown : str
            Markdown project summary provided by the user.
        template_type : str
            Template to follow (etl, api, sql_table, tool).
        page_title : str
            Title for the page being created.
        existing_body : str | None
            If the target page already has content, provide it here so Claude
            can merge rather than overwrite.

        Returns
        -------
        str
            Confluence storage-format XHTML body.
        """
        writing_standards = self._load_writing_standards()
        template = self._load_template(template_type)
        system = CREATE_SYSTEM_PROMPT.format(
            writing_standards=writing_standards,
            template=template,
        )

        parts = [
            f'## Page title\n{page_title}',
            f"## Project summary (source material)\n{source_markdown}",
        ]
        if existing_body:
            parts.append(
                f"## Existing page content (merge into this)\n```xml\n{existing_body}\n```"
            )

        user_msg = "\n\n".join(parts)
        return self._call(system, user_msg, context_label=f"create '{page_title}'")

    # MARK: API Call

    def _call(self, system: str, user_message: str, *, context_label: str) -> str:
        """Send a message to Claude and return the text response.

        Parameters
        ----------
        system : str
            System prompt.
        user_message : str
            User message.
        context_label : str
            Human-readable label for logging.

        Returns
        -------
        str
            Claude's text response.
        """
        logger.info("Calling Claude (%s) — %s", self._model, context_label)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=16_384,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )

        text = response.content[0].text
        logger.info(
            "Claude responded — %d input tokens, %d output tokens",
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        return text
