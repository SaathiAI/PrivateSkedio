import asyncio
import sys
import os
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# ─────────────────────────────────────────────
# 🚨 1. MAGIC PATH FIX (Crucial)
# ─────────────────────────────────────────────
# This ensures Python finds 'src' even if you run from a different folder.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ─────────────────────────────────────────────
# 🔍 2. PRO LOGGING SETUP
# ─────────────────────────────────────────────
# Create a dedicated logger
logger = logging.getLogger("mcp-server")
logger.setLevel(logging.DEBUG)  # Capture everything

# A. File Handler: Rotates logs (Max 5MB, keeps 3 backups)
#    Detailed format: Time | Level | File:Line | Message
file_handler = RotatingFileHandler('mcp_debug.log', maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s')
file_handler.setFormatter(file_formatter)

# B. Console Handler: Prints to stderr (Visible in terminal)
#    Simple format: Just the message
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.INFO) # Only show INFO/ERROR on screen
console_formatter = logging.Formatter('[calendar-mcp] %(message)s')
console_handler.setFormatter(console_formatter)

# Add handlers
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

server = Server("calendar-mcp")

# ─────────────────────────────────────────────
# Tool Definitions
# ─────────────────────────────────────────────
TOOLS = [
    Tool(
        name="create_event",
        description="Create a single Google Calendar event",
        inputSchema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"}, "description": {"type": "string"},
                "start_iso": {"type": "string"}, "end_iso": {"type": "string"},
                "event_id": {"type": "string"},
                "user_id": {"type": "string"}
            },
            "required": ["summary", "description", "start_iso", "end_iso"]
        }
    ),
    Tool(
        name="create_events_from_plan",
        description="Bulk create events from a Plan JSON string",
        inputSchema={
            "type": "object",
            "properties": {"plan_json": {"type": "string"}, "user_id": {"type": "string"}},
            "required": ["plan_json"]
        }
    ),
    Tool(
        name="list_events",
        description="List events in a time range",
        inputSchema={
            "type": "object",
            "properties": {
                "time_min_iso": {"type": "string"}, "time_max_iso": {"type": "string"},
                "max_results": {"type": "integer"},
                "user_id": {"type": "string"}
            },
            "required": ["time_min_iso", "time_max_iso"]
        }
    ),
    Tool(
        name="delete_skedioai_events_in_range",
        description="Delete ONLY SkedioAI events in a time range",
        inputSchema={
            "type": "object",
            "properties": {
                "time_min_iso": {"type": "string"}, "time_max_iso": {"type": "string"},
                "user_id": {"type": "string"}
            },
            "required": ["time_min_iso", "time_max_iso"]
        }
    ),
    Tool(
        name="delete_skedioai_event_by_slot",
        description="Delete a specific skedioai event by date and time",
        inputSchema={
            "type": "object",
            "properties": {
                "date": {"type": "string"}, "start_time": {"type": "string"}, "end_time": {"type": "string"},
                "user_id": {"type": "string"}
            },
            "required": ["date", "start_time", "end_time"]
        }
    ),
    Tool(
        name="mark_event_completed",
        description="Mark a skedioai event as completed",
        inputSchema={
            "type": "object",
            "properties": {
                "date": {"type": "string"}, "start_time": {"type": "string"}, "end_time": {"type": "string"},
                "completed": {"type": "boolean", "default": True},
                "match_key": {"type": "string"},
                "user_id": {"type": "string"}
            },
            "required": ["date", "start_time", "end_time"]
        }
    ),
    Tool(
        name="get_non_skedioai_events",
        description="Check for conflicts (non-skedioai events)",
        inputSchema={
            "type": "object",
            "properties": {
                "start_date": {"type": "string"}, "end_date": {"type": "string"},
                "user_id": {"type": "string"}
            },
            "required": ["start_date", "end_date"]
        }
    )
]

@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS

    # builds HTML email + sends via Gmail SMTP

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    start_ts = time.time()
    logger.info(f"Tool execution started: {name}")
    logger.debug(f"Arguments: {arguments}")
    
    try:
        # Import lazily to ensure 'src' path is ready and avoid startup blocks
        from src.tools.calendar_ops import (
            create_event_core,
            create_events_from_plan_core,
            list_events_core,
            delete_skedioai_events_in_range_core,
            delete_skedioai_event_by_slot_core,
            get_non_skedioai_events_core
        )
        
        loop = asyncio.get_event_loop()
        result = ""

        # Map tools to functions
        if name == "create_event":
            result = await loop.run_in_executor(None, lambda: create_event_core(**arguments))
        elif name == "create_events_from_plan":
            result = await loop.run_in_executor(None, lambda: create_events_from_plan_core(arguments["plan_json"], arguments.get("user_id")))
        elif name == "list_events":
            result = await loop.run_in_executor(None, lambda: list_events_core(arguments["time_min_iso"], arguments["time_max_iso"], arguments.get("max_results", 10), arguments.get("user_id")))
        elif name == "delete_skedioai_events_in_range":
            result = await loop.run_in_executor(None, lambda: delete_skedioai_events_in_range_core(arguments["time_min_iso"], arguments["time_max_iso"], arguments.get("user_id")))
        elif name == "delete_skedioai_event_by_slot":
            result = await loop.run_in_executor(None, lambda: delete_skedioai_event_by_slot_core(arguments["date"], arguments["start_time"], arguments["end_time"], arguments.get("user_id")))
        elif name == "mark_event_completed":
            result = await loop.run_in_executor(None, lambda: mark_event_completed_core(arguments["date"], arguments["start_time"], arguments["end_time"], arguments.get("completed", True), arguments.get("match_key", None), arguments.get("user_id")))
        elif name == "get_non_skedioai_events":
            result = await loop.run_in_executor(None, lambda: get_non_skedioai_events_core(arguments["start_date"], arguments["end_date"], arguments.get("user_id")))
        else:
            raise ValueError(f"Unknown tool: {name}")
        
        duration = time.time() - start_ts
        logger.info(f"Finished {name} in {duration:.2f}s")
        logger.debug(f"Result preview: {str(result)[:200]}...")  

        return [TextContent(type="text", text=str(result))]
        
    except Exception as e:
        duration = time.time() - start_ts
        logger.error(f"Crash in {name} (took {duration:.2f}s): {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        logger.info("Calendar MCP Server started and ready")
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
