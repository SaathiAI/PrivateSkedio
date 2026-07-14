import asyncio
import json
import os
from typing import Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class CalendarClient:
    """MCP Client for Calendar operations"""

    def __init__(self):
        self.session: Optional[ClientSession] = None
        self._connection_ctx = None
        self._session_ctx = None

    async def connect(self):
        """Establish connection to MCP server"""
        if self.session:
            return

        server_params = StdioServerParameters(
            command="python",
            args=["-m", "src.mcp_servers.calendar_mcp_server"],
            env={
                **os.environ,
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
            },
        )

        self._connection_ctx = stdio_client(server_params)
        read_stream, write_stream = await self._connection_ctx.__aenter__()

        self._session_ctx = ClientSession(read_stream, write_stream)
        self.session = await self._session_ctx.__aenter__()

        await self.session.initialize()
        print("Connected to Calendar MCP Server")

    async def disconnect(self):
        """Close connection to MCP server"""
        if self._session_ctx:
            await self._session_ctx.__aexit__(None, None, None)
            self._session_ctx = None
        if self._connection_ctx:
            await self._connection_ctx.__aexit__(None, None, None)
            self._connection_ctx = None
        self.session = None

    async def _call(self, tool_name: str, **kwargs):
        """Internal method to call MCP tools with auto-reconnect on failure."""
        if not self.session:
            await self.connect()

        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        try:
            result = await self.session.call_tool(tool_name, arguments=filtered_kwargs)
            return result.content[0].text
        except Exception:
            await self.disconnect()
            await self.connect()
            result = await self.session.call_tool(tool_name, arguments=filtered_kwargs)
            return result.content[0].text

    # Public API Methods
    async def create_event(self, summary: str, description: str, start_iso: str, end_iso: str, event_id: Optional[str] = None, user_id: Optional[str] = None) -> str:
        return await self._call("create_event", summary=summary, description=description, start_iso=start_iso, end_iso=end_iso, event_id=event_id, user_id=user_id)

    async def create_events_from_plan(self, plan_json: str, user_id: Optional[str] = None) -> str:
        return await self._call("create_events_from_plan", plan_json=plan_json, user_id=user_id)

    async def list_events(self, time_min_iso: str, time_max_iso: str, max_results: int = 10, user_id: Optional[str] = None) -> str:
        return await self._call("list_events", time_min_iso=time_min_iso, time_max_iso=time_max_iso, max_results=max_results, user_id=user_id)

    async def delete_skedioai_events_in_range(self, time_min_iso: str, time_max_iso: str, user_id: Optional[str] = None) -> str:
        return await self._call("delete_skedioai_events_in_range", time_min_iso=time_min_iso, time_max_iso=time_max_iso, user_id=user_id)

    async def delete_skedioai_event_by_slot(self, date: str, start_time: str, end_time: str, user_id: Optional[str] = None) -> str:
        return await self._call("delete_skedioai_event_by_slot", date=date, start_time=start_time, end_time=end_time, user_id=user_id)

    async def mark_event_completed(self, date: str, start_time: str, end_time: str, completed: bool = True, match_key: str = None, user_id: Optional[str] = None) -> str:
        return await self._call("mark_event_completed", date=date, start_time=start_time, end_time=end_time, completed=completed, match_key=match_key, user_id=user_id)

    async def get_non_skedioai_events(self, start_date: str, end_date: str, user_id: Optional[str] = None) -> str:
        return await self._call("get_non_skedioai_events", start_date=start_date, end_date=end_date, user_id=user_id)


# Singleton instance
_global_client: Optional[CalendarClient] = None


def get_calendar_client() -> CalendarClient:
    """Get global calendar client instance"""
    global _global_client
    if _global_client is None:
        _global_client = CalendarClient()
    return _global_client


# Test script
async def test_client():
    """Test the MCP client"""
    client = CalendarClient()

    try:
        await client.connect()

        print("\nTesting list_events...")
        result = await client.list_events(
            time_min_iso="2026-02-10T00:00:00+05:30",
            time_max_iso="2026-02-15T23:59:59+05:30",
            max_results=5
        )
        print(f"Result: {result}\n")

        print("Testing get_non_skedioai_events...")
        result = await client.get_non_skedioai_events(
            start_date="2026-02-10",
            end_date="2026-02-15"
        )
        print(f"Result: {result}\n")

        print("All tests passed!")

    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_client())

