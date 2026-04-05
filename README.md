# Auto PPT Agent

Agent that generates PPT using MCP servers.

## Project Structure

```
auto-ppt-agent/
├── servers/
│   ├── pptx_mcp/          # MCP server for PowerPoint generation
│   ├── wikipedia_mcp/     # MCP server for Wikipedia content fetching
│   ├── image_fetch_mcp/   # MCP server for image fetching
├── client/                # Client that orchestrates the MCP servers
├── frontend/              # Frontend interface
├── outputs/               # Generated PPT files (auto-created)
├── .env                   # Environment variables
├── README.md
```

## Setup

1. Install dependencies for each component:

```bash
pip install -r client/requirements.txt
pip install -r servers/pptx_mcp/requirements.txt
pip install -r servers/wikipedia_mcp/requirements.txt
pip install -r servers/image_fetch_mcp/requirements.txt
```

2. Copy `.env` and fill in your API keys:

```
HF_API_TOKEN=your_huggingface_token
PEXELS_API_KEY=your_pexels_api_key
```

3. The `outputs/` directory will be created automatically when the agent runs.
