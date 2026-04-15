"""MCP server authentication — bearer token validation."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastmcp import Context

load_dotenv()


def resolve_expected_admin_token() -> str:
    token = os.getenv("ADMIN_TOKEN", "").strip()
    if not token:
        raise RuntimeError("ADMIN_TOKEN is required for MCP server authentication")
    return token


def _extract_bearer_token(ctx: Context) -> str:
    request_context = ctx.request_context
    if request_context is None or request_context.request is None:
        return ""

    auth_header = request_context.request.headers.get("authorization", "")
    prefix = "Bearer "
    if auth_header.startswith(prefix):
        return auth_header[len(prefix):].strip()
    return ""


def require_authorized(ctx: Context) -> None:
    expected = resolve_expected_admin_token()
    supplied = _extract_bearer_token(ctx)
    if not supplied or supplied != expected:
        raise PermissionError("Unauthorized")
