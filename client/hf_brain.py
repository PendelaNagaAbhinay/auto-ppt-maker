import httpx
import json
import os
from dotenv import dotenv_values

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class HFBrain:
    def __init__(self):
        # Load environment variables
        env_file = os.path.join(PROJECT_ROOT, "servers", ".env")
        env_vars = dotenv_values(env_file) if os.path.exists(env_file) else os.environ
        
        hf_token = env_vars.get("HF_API_TOKEN", "")
        
        self.model = "Qwen/Qwen2.5-72B-Instruct"
        self.url = "https://router.huggingface.co/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {hf_token}",
            "Content-Type": "application/json"
        }
        self.tools = []
        self.reset()
        
    def reset(self):
        self.history = []
        system_prompt = """You are an AI assistant that generates educational slide content.

Rules:
- Always respond in JSON format when generating slides
- Format:
{
  "title": "string",
  "bullets": ["point1", "point2", "point3"]
}
- Use simple language (for school students)
- Each bullet max 120 characters
- Use 3–5 bullet points"""
        
        self.history.append({"role": "system", "content": system_prompt})
        
    def set_tools(self, tools):
        self.tools = tools

    def chat(self, user_message):
        self.history.append({"role": "user", "content": user_message})
        
        print("Sending request to HF")
        payload = {
            "model": self.model,
            "messages": self.history,
            "temperature": 0.3
        }
        
        if self.tools:
            payload["tools"] = self.tools
            payload["tool_choice"] = "auto"
            
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(self.url, headers=self.headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            print(f"API Error: {e}")
            return "ERROR: API failed"
            
        print("Received response")
        
        try:
            assistant_message = data["choices"][0]["message"]
            self.history.append(assistant_message)
            return data
        except (KeyError, IndexError) as e:
            print(f"Response format Error: {e}")
            return "ERROR: API failed"

    def parse_tool_call(self, response):
        if isinstance(response, str) and response.startswith("ERROR"):
            return None
            
        try:
            message = response["choices"][0]["message"]
            if "tool_calls" in message and message["tool_calls"]:
                tool_call = message["tool_calls"][0]
                tool_name = tool_call["function"]["name"]
                arguments_dict = json.loads(tool_call["function"]["arguments"])
                return tool_name, arguments_dict
        except Exception as e:
            print(f"Parse tool call error: {e}")
        
        return None

    def inject_tool_result(self, tool_name, result):
        self.history.append({
            "role": "tool",
            "name": tool_name,
            "content": result
        })

    def generate_slide_content(self, topic, research_text):
        prompt = f"""Create slide content for:
Topic: {topic}

Use this information:
{research_text}

Return JSON only."""

        response = self.chat(prompt)
        
        if isinstance(response, str) and response.startswith("ERROR"):
            return {
                "title": topic,
                "bullets": ["Basic explanation...", "Key points...", "Conclusion..."]
            }
            
        try:
            message = response["choices"][0]["message"]["content"]
            message = message.strip()
            # Sometimes models wrap json in markdown block
            if message.startswith("```json"):
                message = message[7:]
            elif message.startswith("```"):
                message = message[3:]
                
            if message.endswith("```"):
                message = message[:-3]
            
            return json.loads(message.strip())
        except Exception as e:
            print(f"JSON Parse Error: {e}")
            return {
                "title": topic,
                "bullets": ["Basic explanation...", "Key points...", "Conclusion..."]
            }
