from __future__ import annotations

import logging
from dataclasses import dataclass, field

import requests

from src.config import Config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PageContent:
    """A single Confluence page's metadata and storage-format body."""

    page_id: str
    title: str
    version: int
    body: str
    space_key: str = ""
    parent_id: str = ""


@dataclass(frozen=True)
class PageNode:
    """Lightweight node used when walking the Confluence page tree.

    Attributes
    ----------
    page_id : str
        Confluence content ID.
    title : str
        Page or folder title.
    content_type : str
        "page" or "folder".
    parent_id : str
        Parent content ID.
    children : list[PageNode]
        Direct children of this node.
    """

    page_id: str
    title: str
    content_type: str = "page"
    parent_id: str = ""
    children: list[PageNode] = field(default_factory=list)


class ConfluenceClient:
    """Client for Atlassian Confluence Cloud REST API (v1 for pages, v2 for tree discovery).

    Parameters
    ----------
    cfg : Config
        Application configuration with Confluence credentials.
    """

    def __init__(self, cfg: Config) -> None:
        self._wiki_base = cfg.confluence_base_url
        self._v1 = f"{cfg.confluence_base_url}/rest/api"
        self._v2 = f"{cfg.confluence_base_url}/api/v2"
        self._session = requests.Session()
        self._session.auth = (cfg.confluence_user_email, cfg.confluence_token)
        self._session.headers["Accept"] = "application/json"

    # MARK: Page Read (v1)

    def get_page(self, page_id: str) -> PageContent:
        """Fetch a single page including its storage-format body.

        Parameters
        ----------
        page_id : str
            Confluence page ID.

        Returns
        -------
        PageContent
            Page metadata and body content.
        """
        resp = self._session.get(
            f"{self._v1}/content/{page_id}",
            params={"expand": "body.storage,version,space,ancestors"},
        )
        resp.raise_for_status()
        data = resp.json()

        ancestors = data.get("ancestors", [])
        parent_id = str(ancestors[-1]["id"]) if ancestors else ""

        return PageContent(
            page_id=page_id,
            title=data["title"],
            version=data["version"]["number"],
            body=data["body"]["storage"]["value"],
            space_key=data.get("space", {}).get("key", ""),
            parent_id=parent_id,
        )

    # MARK: Tree Discovery (v2 — supports folders)

    def get_page_children_v2(self, page_id: str) -> list[PageNode]:
        """List direct children of a page — both child pages and child folders.

        The v2 ``pages/{id}/children`` endpoint only returns child pages,
        so we also query v1 ``content/{id}/child/folder`` to pick up folders.

        Parameters
        ----------
        page_id : str
            Parent page ID.

        Returns
        -------
        list[PageNode]
            Child nodes (pages and folders) with content_type set.
        """
        # v2 for child pages
        children = self._paginate_children(f"{self._v2}/pages/{page_id}/children", page_id)

        # v1 for child folders (v2 has no single endpoint for this)
        children.extend(self._get_child_folders_v1(page_id))

        return children

    def _get_child_folders_v1(self, page_id: str) -> list[PageNode]:
        """Fetch child folders of a page using the v1 API.

        Parameters
        ----------
        page_id : str
            Parent page ID.

        Returns
        -------
        list[PageNode]
            Child folder nodes.
        """
        folders: list[PageNode] = []
        url: str | None = f"{self._v1}/content/{page_id}/child/folder"
        params: dict[str, str | int] = {"limit": 100}

        while url:
            resp = self._session.get(url, params=params)
            if resp.status_code == 404:
                break
            resp.raise_for_status()
            data = resp.json()

            for result in data.get("results", []):
                folders.append(PageNode(
                    page_id=str(result["id"]),
                    title=result["title"],
                    content_type="folder",
                    parent_id=page_id,
                ))

            next_link = data.get("_links", {}).get("next")
            if next_link:
                url = f"{self._wiki_base}{next_link}"
                params = {}
            else:
                url = None

        return folders

    def get_folder_children_v2(self, folder_id: str) -> list[PageNode]:
        """List direct children of a folder using the v2 API.

        Parameters
        ----------
        folder_id : str
            Parent folder ID.

        Returns
        -------
        list[PageNode]
            Child nodes with content_type set.
        """
        return self._paginate_children(f"{self._v2}/folders/{folder_id}/direct-children", folder_id)

    def get_page_tree(self, root_id: str, *, max_depth: int = 10) -> PageNode:
        """Recursively walk the content tree starting from a page or folder.

        Uses the v2 API so that folders and their children are included.

        Parameters
        ----------
        root_id : str
            Page or folder ID to start from.
        max_depth : int
            Maximum recursion depth.

        Returns
        -------
        PageNode
            Tree of nodes with children populated.
        """
        content_type, title = self._identify_content(root_id)
        return self._walk_tree(root_id, title=title, content_type=content_type,
                               parent_id="", depth=0, max_depth=max_depth)

    def get_space_root_pages(self, space_key: str) -> list[PageNode]:
        """List top-level pages in a Confluence space.

        Parameters
        ----------
        space_key : str
            Confluence space key (e.g. "ENG").

        Returns
        -------
        list[PageNode]
            Root-level page nodes in the space.
        """
        pages: list[PageNode] = []
        url: str | None = f"{self._v1}/content"
        params: dict[str, str | int] = {
            "spaceKey": space_key,
            "type": "page",
            "depth": "root",
            "limit": 100,
        }

        while url:
            resp = self._session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            for result in data.get("results", []):
                pages.append(PageNode(
                    page_id=str(result["id"]),
                    title=result["title"],
                    content_type="page",
                ))

            next_link = data.get("_links", {}).get("next")
            if next_link:
                url = f"{self._wiki_base}{next_link}"
                params = {}
            else:
                url = None

        return pages

    # MARK: Page Write (v1)

    def update_page(self, page_id: str, title: str, body: str, current_version: int) -> dict:
        """Write new storage-format body to an existing Confluence page.

        Parameters
        ----------
        page_id : str
            Target page ID.
        title : str
            Page title (must match or be the desired new title).
        body : str
            Confluence storage-format XHTML body.
        current_version : int
            Current page version (will be incremented).

        Returns
        -------
        dict
            Confluence API response.
        """
        payload = {
            "id": page_id,
            "type": "page",
            "title": title,
            "version": {"number": current_version + 1},
            "body": {
                "storage": {
                    "value": body,
                    "representation": "storage",
                }
            },
        }
        resp = self._session.put(f"{self._v1}/content/{page_id}", json=payload)
        resp.raise_for_status()
        logger.info(
            "Updated page '%s' [%s] (v%d -> v%d)",
            title, page_id, current_version, current_version + 1,
        )
        return resp.json()

    def create_page(
        self, space_key: str, title: str, body: str, parent_id: str | None = None
    ) -> dict:
        """Create a new Confluence page.

        Parameters
        ----------
        space_key : str
            Target space key.
        title : str
            Page title.
        body : str
            Confluence storage-format XHTML body.
        parent_id : str | None
            Parent page or folder ID. If None, creates at space root.

        Returns
        -------
        dict
            Confluence API response including the new page ID.
        """
        payload: dict = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": body,
                    "representation": "storage",
                }
            },
        }
        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]

        resp = self._session.post(f"{self._v1}/content", json=payload)
        resp.raise_for_status()
        new_id = resp.json()["id"]
        logger.info("Created page '%s' [%s] in space %s", title, new_id, space_key)
        return resp.json()

    # MARK: Helpers

    def _identify_content(self, content_id: str) -> tuple[str, str]:
        """Determine whether a content ID is a page or folder and get its title.

        Parameters
        ----------
        content_id : str
            Confluence content ID.

        Returns
        -------
        tuple[str, str]
            (content_type, title) — content_type is "page" or "folder".
        """
        # Try as page first (most common)
        resp = self._session.get(f"{self._v2}/pages/{content_id}")
        if resp.status_code == 200:
            return "page", resp.json().get("title", "")

        # Try as folder
        resp = self._session.get(f"{self._v2}/folders/{content_id}")
        if resp.status_code == 200:
            return "folder", resp.json().get("title", "")

        # Fallback to v1 (catches other content types)
        resp = self._session.get(f"{self._v1}/content/{content_id}")
        resp.raise_for_status()
        data = resp.json()
        return data.get("type", "page"), data.get("title", "")

    def _paginate_children(self, initial_url: str, parent_id: str) -> list[PageNode]:
        """Fetch all children from a paginated v2 endpoint.

        Parameters
        ----------
        initial_url : str
            The v2 API URL to fetch children from.
        parent_id : str
            Parent content ID (for logging and node metadata).

        Returns
        -------
        list[PageNode]
            Child nodes.
        """
        children: list[PageNode] = []
        url: str | None = initial_url
        params: dict[str, str | int] = {"limit": 100}

        while url:
            resp = self._session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            for result in data.get("results", []):
                child_id = str(result.get("id", ""))
                child_title = result.get("title", "")
                child_type = result.get("type", "page")

                children.append(PageNode(
                    page_id=child_id,
                    title=child_title,
                    content_type=child_type,
                    parent_id=parent_id,
                ))

            next_link = data.get("_links", {}).get("next")
            if next_link:
                url = f"{self._wiki_base}{next_link}" if next_link.startswith("/") else next_link
                params = {}
            else:
                url = None

        return children

    def _walk_tree(
        self,
        node_id: str,
        title: str,
        content_type: str,
        parent_id: str,
        depth: int,
        max_depth: int,
    ) -> PageNode:
        """Recursively build a tree of pages and folders."""
        children: list[PageNode] = []

        if depth < max_depth:
            if content_type == "folder":
                child_nodes = self.get_folder_children_v2(node_id)
            else:
                child_nodes = self.get_page_children_v2(node_id)

            for child in child_nodes:
                # Only recurse into pages and folders
                if child.content_type in ("page", "folder"):
                    children.append(
                        self._walk_tree(
                            child.page_id, title=child.title,
                            content_type=child.content_type,
                            parent_id=node_id, depth=depth + 1, max_depth=max_depth,
                        )
                    )

        return PageNode(
            page_id=node_id,
            title=title,
            content_type=content_type,
            parent_id=parent_id,
            children=children,
        )
