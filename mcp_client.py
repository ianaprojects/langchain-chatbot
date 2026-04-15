"""Thin MCP client bridge for calling parking-storage server tools."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from fastmcp import Client
from dotenv import load_dotenv


_LOGGER = logging.getLogger(__name__)


load_dotenv()


class MCPClientError(RuntimeError):
    """Raised when MCP client operations fail."""


def _run_async_safe(coro: Any) -> Any:
    """Run async coroutine, handling Windows asyncio cleanup errors gracefully."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    def ignore_aiohttp_ssl_eror(loop, context):
        # Suppress harmless Windows asyncio connection cleanup errors
        if isinstance(context.get("exception"), ConnectionResetError):
            return
        loop.default_exception_handler(context)
    
    loop.set_exception_handler(ignore_aiohttp_ssl_eror)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()



def _resolve_mcp_server_url() -> str:
    url = os.getenv("MCP_SERVER_URL", "").strip()
    if not url:
        raise MCPClientError("MCP_SERVER_URL is required (example: http://127.0.0.1:8001/mcp)")
    return url


def _resolve_admin_token() -> str:
    token = os.getenv("ADMIN_TOKEN", "").strip()
    if not token:
        raise MCPClientError("ADMIN_TOKEN is required")
    return token


async def _save_reservation_async(reservation: dict[str, Any]) -> str:
    url = _resolve_mcp_server_url()
    token = _resolve_admin_token()

    async with Client(url, auth=token) as client:
        result = await client.call_tool("save_reservation", {"reservation": reservation})

    # FastMCP returns structured content blocks; stringifying keeps integration simple.
    return str(result)


async def _health_check_async(timeout_seconds: float = 2.0) -> None:
    url = _resolve_mcp_server_url()
    token = _resolve_admin_token()

    async with Client(url, auth=token, timeout=timeout_seconds, init_timeout=timeout_seconds) as client:
        await client.list_tools()


def check_mcp_server_health(timeout_seconds: float = 2.0) -> tuple[bool, str]:
    """Verify MCP server connectivity and auth without mutating state."""
    try:
        _run_async_safe(_health_check_async(timeout_seconds=timeout_seconds))
        return (True, "MCP storage is reachable")
    except Exception as exc:
        _LOGGER.warning("MCP health check failed: %s", exc)
        return (False, f"MCP storage unavailable: {exc}")


def save_reservation_via_mcp(
    reservation: dict[str, Any],
    *,
    retries: int = 2,
    retry_delay_seconds: float = 0.4,
) -> str:
    """Call save_reservation on MCP server with minimal retry and logging."""
    last_error: Exception | None = None

    for attempt in range(1, retries + 2):
        try:
            return _run_async_safe(_save_reservation_async(reservation))
        except Exception as exc:
            last_error = exc
            _LOGGER.exception("MCP save_reservation attempt %s failed", attempt)
            if attempt > retries:
                break
            time.sleep(retry_delay_seconds)

    raise MCPClientError(f"MCP save_reservation failed after retries: {last_error}")
