"""
Wikipedia MCP Server — Fetches Wikipedia content via FastMCP tools.

Run:
    python server.py
"""

import json
import logging
import os
import traceback

import wikipediaapi
from fastmcp import FastMCP

# ──────────────────────────────────────────────
# Logging  (file-based — stderr is reserved for MCP stdio transport)
# ──────────────────────────────────────────────
_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wikipedia_mcp.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
    filename=_log_path,
    filemode="a",
)
logger = logging.getLogger("wikipedia_mcp")

# ──────────────────────────────────────────────
# Wikipedia client
# ──────────────────────────────────────────────
wiki = wikipediaapi.Wikipedia(
    user_agent="auto-ppt-agent",
    language="en",
)

# Sections to skip — typically boilerplate / non-content
SKIP_SECTIONS = {
    "See also",
    "References",
    "External links",
    "Further reading",
    "Notes",
    "Bibliography",
    "Sources",
    "Footnotes",
    "Citations",
}

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _truncate_sentences(text: str, sentences: int, max_chars: int = None) -> str:
    """Return the first *sentences* sentences from *text*, optionally bounded by max_chars."""
    parts = text.split(". ")
    if len(parts) <= sentences:
        truncated = text
    else:
        truncated = ". ".join(parts[:sentences]) + "."
    
    # Clean output: Remove extra whitespace
    truncated = " ".join(truncated.split())

    if max_chars and len(truncated) > max_chars:
        truncated = truncated[:max_chars - 3] + "..."
    return truncated


def _collect_sections(sections, depth: int = 0, max_depth: int = 2) -> list[dict]:
    """
    Recursively collect section title + content, skipping irrelevant ones.
    """
    result: list[dict] = []
    for section in sections:
        if section.title in SKIP_SECTIONS:
            continue
        content = " ".join(section.text.strip().split())
        if content:
            # First 2 sentences, max 300 chars
            result.append({
                "title": section.title,
                "content": _truncate_sentences(content, sentences=2, max_chars=300),
            })
        if depth < max_depth:
            result.extend(_collect_sections(section.sections, depth + 1, max_depth))
    return result


def _get_page_resolved(topic: str):
    """Fetch page, resolving disambiguation to the first valid link if necessary."""
    page = wiki.page(topic)
    if not page.exists():
        return None
    
    summary = page.summary.strip()
    if summary.endswith("may refer to:") or "disambiguation" in page.title.lower():
        # Disambiguation page
        if page.links:
            # Pick first valid link
            first_link_title = list(page.links.keys())[0]
            page = wiki.page(first_link_title)
            if not page.exists():
                return None
    return page


# ──────────────────────────────────────────────
# FastMCP Server
# ──────────────────────────────────────────────
mcp = FastMCP("wikipedia_mcp")


@mcp.tool
def get_summary(topic: str, sentences: int = 5) -> str:
    """
    Get a plain-text summary of a Wikipedia topic.

    Args:
        topic:     The Wikipedia article title to look up.
        sentences: Maximum number of sentences to return (default 5).

    Returns:
        Plain text summary, or "NOT_FOUND:{topic}" if the page doesn't exist.
    """
    logger.info("Fetching summary for %s", topic)

    try:
        page = _get_page_resolved(topic)

        if not page:
            return f"NOT_FOUND:{topic}"

        summary = " ".join(page.summary.split())
        if not summary:
            return f"NOT_FOUND:{topic}"

        summary = _truncate_sentences(summary, sentences)
        return summary

    except Exception as e:
        logger.error("get_summary failed: %s", e)
        return f"ERROR: {str(e)}"


@mcp.tool
def get_sections(topic: str) -> str:
    """
    Get the sections of a Wikipedia article as a JSON string.

    Returns a JSON array of objects: [{"title": "...", "content": "..."}]
    Irrelevant sections (References, See also, etc.) are automatically skipped.

    Args:
        topic: The Wikipedia article title to look up.

    Returns:
        JSON string with sections, or "[]" if not found or empty.
    """
    logger.info("Fetching sections for %s", topic)

    try:
        page = _get_page_resolved(topic)

        if not page:
            return "[]"

        sections = _collect_sections(page.sections)
        
        # Limit to max 5 sections
        sections = sections[:5]

        if not sections:
            return "[]"

        return json.dumps(sections, ensure_ascii=False)

    except Exception as e:
        logger.error("get_sections failed: %s", e)
        return f"ERROR: {str(e)}"


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("Starting Wikipedia MCP Server …")
    mcp.run()
