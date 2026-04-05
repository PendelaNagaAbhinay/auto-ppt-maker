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
    user_agent="auto-ppt-agent/1.0 (MCP server; educational project)",
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

def _truncate_summary(text: str, sentences: int) -> str:
    """Return the first *sentences* sentences from *text*."""
    # Split on '. ' to get sentence boundaries (simple heuristic)
    parts = text.split(". ")
    if len(parts) <= sentences:
        return text
    return ". ".join(parts[:sentences]) + "."


def _collect_sections(sections, depth: int = 0, max_depth: int = 2) -> list[dict]:
    """
    Recursively collect section title + content, skipping irrelevant ones.
    Limits recursion to *max_depth* levels to avoid huge payloads.
    """
    result: list[dict] = []
    for section in sections:
        if section.title in SKIP_SECTIONS:
            continue
        content = section.text.strip()
        if content:
            result.append({
                "title": section.title,
                "content": content,
            })
        # Recurse into subsections
        if depth < max_depth:
            result.extend(_collect_sections(section.sections, depth + 1, max_depth))
    return result


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
    logger.info("get_summary(topic=%r, sentences=%d)", topic, sentences)

    try:
        page = wiki.page(topic)

        if not page.exists():
            logger.warning("Page not found: %s", topic)
            return f"NOT_FOUND:{topic}"

        summary = _truncate_summary(page.summary, sentences)
        logger.info("Summary fetched for %r (%d chars).", topic, len(summary))
        return summary

    except Exception:
        tb = traceback.format_exc()
        logger.error("get_summary failed:\n%s", tb)
        return json.dumps({
            "status": "error",
            "message": f"Failed to fetch summary for '{topic}'.",
            "details": tb,
        })


@mcp.tool
def get_sections(topic: str) -> str:
    """
    Get the sections of a Wikipedia article as a JSON string.

    Returns a JSON array of objects: [{"title": "...", "content": "..."}]
    Irrelevant sections (References, See also, etc.) are automatically skipped.

    Args:
        topic: The Wikipedia article title to look up.

    Returns:
        JSON string with sections, or "NOT_FOUND:{topic}" if the page doesn't exist.
    """
    logger.info("get_sections(topic=%r)", topic)

    try:
        page = wiki.page(topic)

        if not page.exists():
            logger.warning("Page not found: %s", topic)
            return f"NOT_FOUND:{topic}"

        sections = _collect_sections(page.sections)
        logger.info("Sections fetched for %r (%d sections).", topic, len(sections))
        return json.dumps(sections, ensure_ascii=False)

    except Exception:
        tb = traceback.format_exc()
        logger.error("get_sections failed:\n%s", tb)
        return json.dumps({
            "status": "error",
            "message": f"Failed to fetch sections for '{topic}'.",
            "details": tb,
        })


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("Starting Wikipedia MCP Server …")
    mcp.run()
