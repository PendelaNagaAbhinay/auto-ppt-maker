import json
import os
import re

class AgentLoop:
    def __init__(self, mcp_manager, hf_brain):
        self.mcp = mcp_manager
        self.brain = hf_brain

    def validate_plan(self, slides):
        if not isinstance(slides, list):
            return False
        if not (3 <= len(slides) <= 7):
            return False
        for slide in slides:
            if not isinstance(slide, str) or len(slide) <= 3:
                return False
        return True

    def clean_bullets(self, bullets):
        if not isinstance(bullets, list):
            return []
            
        cleaned = []
        for bullet in bullets:
            if not isinstance(bullet, str):
                continue
                
            b = bullet.strip()
            if not b:
                continue
                
            if len(b) > 120:
                b = b[:117] + "..."
                
            cleaned.append(b)
            if len(cleaned) == 5:
                break
                
        return cleaned
        
    def _parse_json(self, response_data):
        if isinstance(response_data, str) and response_data.startswith("ERROR"):
            return None
            
        try:
            # Extract content from HF schema
            content = response_data["choices"][0]["message"]["content"]
            content = content.strip()
            
            # Strip markdown wrappers
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
                
            if content.endswith("```"):
                content = content[:-3]
                
            return json.loads(content.strip())
        except Exception:
            return None

    async def run(self, user_prompt: str) -> str:
        # STEP 1 — PLAN
        prompt = f"Generate 5 slide titles for:\n{user_prompt}\n\nReturn as JSON array only."
        raw_response = self.brain.chat(prompt)
        slides = self._parse_json(raw_response)
        
        # VALIDATE PLAN
        if not self.validate_plan(slides):
            retry_prompt = "Invalid format. Return an array of strings representing slide titles only. Length 3-7. Example: [\"Intro\", \"Details\"]. Return JSON array only."
            raw_response = self.brain.chat(retry_prompt)
            slides = self._parse_json(raw_response)
            
            if not self.validate_plan(slides):
                slides = ["Introduction", "Main Concept", "Details", "Applications", "Conclusion"]

        print("PLAN:", slides)

        # STEP 2 — CREATE PRESENTATION
        # Pass empty dict since theme defaults to 'default'
        await self.mcp.call_tool("create_presentation", {})

        # STEP 3 — LOOP THROUGH SLIDES
        for slide_title in slides:
            # STEP 3A — RESEARCH
            try:
                summary = await self.mcp.call_tool(
                    "get_summary",
                    {"topic": slide_title, "sentences": 3}
                )
            except Exception:
                summary = "ERROR"
                
            if "NOT_FOUND" in summary or "ERROR" in summary:
                summary = f"Basic explanation of {slide_title}"

            # STEP 3B — GENERATE CONTENT
            try:
                content = self.brain.generate_slide_content(slide_title, summary)
            except Exception:
                content = None
                
            if not isinstance(content, dict) or "title" not in content or "bullets" not in content:
                content = {
                    "title": slide_title,
                    "bullets": ["Basic info", "Key idea", "Example"]
                }
                
            # CLEAN BULLETS
            content["bullets"] = self.clean_bullets(content["bullets"])
            
            # Ensure fallback if empty after cleaning
            if not content["bullets"]:
                content["bullets"] = ["Basic info"]

            # STEP 3C — ADD SLIDE
            try:
                await self.mcp.call_tool(
                    "add_slide",
                    {
                        "title": content["title"],
                        "bullets": content["bullets"]
                    }
                )
                print("Added slide:", slide_title)
            except Exception as e:
                print(f"Error adding slide '{slide_title}': {e}")
                continue

        # STEP 4 — SAVE
        safe_name = os.path.basename(user_prompt)[:10].replace(" ", "_")
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '', safe_name)
        if not safe_name:
            safe_name = "presentation"
            
        output_path = os.path.abspath(f"outputs/{safe_name}.pptx")

        try:
            await self.mcp.call_tool(
                "save_presentation",
                {"output_path": output_path}
            )
            print("Saved output to:", output_path)
        except Exception as e:
            print(f"Error saving presentation: {e}")

        # RETURN
        return output_path
