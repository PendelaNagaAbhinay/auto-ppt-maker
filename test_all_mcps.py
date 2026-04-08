import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

results = []

def log(server, tool, status, message=""):
    results.append(f"[{server}] {tool} -> {status} {message}")
    print(results[-1])

print("--- Testing PPTX MCP ---")
try:
    from servers.pptx_mcp.server import (
        create_presentation, add_slide, add_image_slide, set_theme, save_presentation
    )
    # Test 1
    res = create_presentation("default")
    log("pptx_mcp", "create_presentation", "OK" if "success" in res else "FAIL", res)
    
    # Test 2
    res = set_theme("000000", "FFFFFF", "CCCCCC")
    log("pptx_mcp", "set_theme", "OK" if "success" in res else "FAIL", res)
    
    # Test 3
    res = add_slide("Test Title", ["Bullet 1", "Bullet 2"])
    log("pptx_mcp", "add_slide", "OK" if "success" in res else "FAIL", res)
    
    # Test 4 (Image slide - need a dummy image or expect safe failure)
    res = add_image_slide("Image Title", "does_not_exist.jpg", "caption")
    log("pptx_mcp", "add_image_slide (invalid)", "OK" if "Error" in res or "not found" in res else "FAIL", res)
    
    # Test 5
    res = save_presentation("outputs/test.pptx")
    log("pptx_mcp", "save_presentation", "OK" if "success" in res else "FAIL", res)

except Exception as e:
    log("pptx_mcp", "ALL", "CRITICAL FAIL", str(e))


print("\n--- Testing Wikipedia MCP ---")
try:
    from servers.wikipedia_mcp.server import get_summary, get_sections
    
    # Test 1
    res = get_summary("Python_(programming_language)", 2)
    log("wikipedia_mcp", "get_summary (valid)", "OK" if "Python" in res and not res.startswith("ERROR") else "FAIL", res[:50] + "...")
    
    # Test 2
    res = get_summary("ThisPageDoesNotExist1234567890", 2)
    log("wikipedia_mcp", "get_summary (invalid)", "OK" if res.startswith("NOT_FOUND") else "FAIL", res)
    
    # Test 3
    res = get_sections("Jaguar")
    log("wikipedia_mcp", "get_sections (valid)", "OK" if "title" in res and "content" in res else "FAIL", "Returned " + str(len(res)) + " bytes")

except Exception as e:
    log("wikipedia_mcp", "ALL", "CRITICAL FAIL", str(e))


print("\n--- Testing Image Fetch MCP ---")
import json
try:
    from servers.image_fetch_mcp.server import search_image, download_image
    
    # Test 1
    res = search_image("cat", 1)
    if "ERROR" in res:
         log("image_fetch_mcp", "search_image", "FAIL", res)
         test_image_url = None
    else:
         data = json.loads(res)
         log("image_fetch_mcp", "search_image (valid)", "OK" if len(data) > 0 else "FAIL", f"Found {len(data)} images")
         if len(data) > 0:
             test_image_url = data[0].get("url")

    # Test 2
    res = search_image("afkjsdfkjejfwq", 1)
    # Pexels sometimes returns a fallback image even for gibberish
    try:
        parsed = json.loads(res)
        is_valid = isinstance(parsed, list)
    except:
        is_valid = False
    log("image_fetch_mcp", "search_image (gibberish/empty)", "OK" if is_valid else "FAIL", "Returned valid JSON list" if is_valid else res)

    # Test 3
    if test_image_url:
         res = download_image(test_image_url, "outputs/images/test_cat.jpg")
         log("image_fetch_mcp", "download_image", "OK" if "test_cat.jpg" in res else "FAIL", res)
    else:
         log("image_fetch_mcp", "download_image", "SKIPPED", "No image URL found from search_image")

except Exception as e:
    log("image_fetch_mcp", "ALL", "CRITICAL FAIL", str(e))

print("\n--- FINAL REPORT ---")
print("\n".join(results))
