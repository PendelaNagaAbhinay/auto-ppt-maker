"""
Image Fetch MCP Server — Searches and downloads images from Pexels via FastMCP tools.

Run:
    python server.py
"""

import json
import logging
import os
import traceback
import requests
from dotenv import load_dotenv

from fastmcp import FastMCP

# ──────────────────────────────────────────────
# Logging (file-based — stderr is reserved for MCP stdio transport)
# ──────────────────────────────────────────────
_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "image_fetch_mcp.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
    filename=_log_path,
    filemode="a",
)
logger = logging.getLogger("image_fetch_mcp")

# ──────────────────────────────────────────────
# Environment Setup
# ──────────────────────────────────────────────
load_dotenv()
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

if not PEXELS_API_KEY:
    logger.error("PEXELS_API_KEY is missing from environment.")

# ──────────────────────────────────────────────
# FastMCP Server
# ──────────────────────────────────────────────
mcp = FastMCP("image_fetch_mcp")


@mcp.tool
def search_image(query: str, count: int = 3) -> str:
    """
    Search Pexels for images matching a query.

    Args:
        query: The search term.
        count: The number of images to return (max 5).

    Returns:
        JSON string list of items: [{"url": "...", "photographer": "...", "width": int, "height": int}]
        Returns "[]" if no results or if an error occurs.
    """
    logger.info("Searching image for %s", query)

    if not PEXELS_API_KEY:
        return "ERROR: PEXELS_API_KEY is missing from environment"

    try:
        count = min(count, 5)
        headers = {"Authorization": PEXELS_API_KEY}
        params = {
            "query": query,
            "per_page": count,
            "orientation": "landscape"
        }

        response = requests.get(
            "https://api.pexels.com/v1/search",
            headers=headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        photos = data.get("photos", [])

        if not photos:
            return "[]"

        results = []
        for photo in photos:
            results.append({
                "url": photo.get("src", {}).get("medium", ""),
                "photographer": photo.get("photographer", ""),
                "width": photo.get("width", 0),
                "height": photo.get("height", 0)
            })

        return json.dumps(results, ensure_ascii=False)

    except Exception as e:
        logger.error("search_image API failure: %s", str(e))
        return "[]"


@mcp.tool
def download_image(url: str, output_path: str) -> str:
    """
    Download an image URL and save it to the specified output path.

    Args:
        url: The direct image link to download.
        output_path: The local filesystem path to save the image (e.g. outputs/images/cat.jpg).

    Returns:
        The output_path on success, or an ERROR string on failure.
    """
    logger.info("Downloading image to %s", output_path)

    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            return "ERROR: download failed"

        return os.path.abspath(output_path)

    except Exception as e:
        logger.error("download_image failure: %s", str(e))
        return "ERROR: download failed"


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    if not PEXELS_API_KEY:
        print("WARNING: PEXELS_API_KEY environment variable is missing.")
    logger.info("Starting Image Fetch MCP Server …")
    mcp.run()
