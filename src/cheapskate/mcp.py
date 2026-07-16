"""
Cheapskate Agent Memory — MCP server (stdio transport).

JSON-RPC 2.0 protocol over stdin/stdout:
- Request:  {"jsonrpc":"2.0","method":"...","params":{...},"id":N}
- Response: {"jsonrpc":"2.0","result":{...},"id":N}
- Error:    {"jsonrpc":"2.0","error":{"code":N,"message":"..."},"id":N}
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from cheapskate.client import MemoryClient
from cheapskate.commands.suggest import get_suggestions


TOOL_HANDLERS = {
    "memory_add": "add",
    "memory_search": "search",
    "memory_list": "list",
    "memory_stats": "stats",
    "memory_status": "status",
    "memory_topicify": "topicify",
}


def _memory_dir() -> Path:
    return Path(os.environ.get("CHEAPSKATE_MEMORY_DIR", Path.home() / ".memory"))


def _handle_request(request: Dict[str, Any]) -> Dict[str, Any]:
    req_id = request.get("id")
    method = request.get("method")
    params: Dict[str, Any] = request.get("params") or {}

    if not method or not isinstance(method, str):
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": "Invalid Request: missing method"},
            "id": req_id,
        }

    try:
        if method == "memory_suggest":
            return _handle_suggest(req_id, params)

        handler_name = TOOL_HANDLERS.get(method)
        if not handler_name:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {method}"},
                "id": req_id,
            }

        client = MemoryClient(memory_dir=_memory_dir())
        method_fn = getattr(client, handler_name)
        result = method_fn(**params)
        client.close()

        payload: Dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}
        if isinstance(result, (dict, list)):
            payload["result"] = result
        else:
            payload["result"] = {"value": result}
        return payload
    except Exception as exc:  # noqa: BLE001
        return {
            "jsonrpc": "2.0",
            "error": {"code": 1, "message": str(exc)},
            "id": req_id,
        }


def _handle_suggest(req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle memory_suggest — returns actual suggestions via get_suggestions()."""
    project = params.get("project", "default")
    limit = int(params.get("limit", 5))

    memory_dir = params.get("memory_dir")
    if isinstance(memory_dir, str):
        memory_dir = Path(memory_dir)

    suggestions = get_suggestions(project=project, memory_dir=memory_dir, limit=limit)

    return {
        "jsonrpc": "2.0",
        "result": {
            "project": project,
            "count": len(suggestions),
            "suggestions": suggestions,
        },
        "id": req_id,
    }


def serve() -> None:
    if sys.version_info >= (3, 13):
        sys.stdin.reconfigure(line_buffering=True)
    else:
        sys.stdin.flush()

    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
                "id": None,
            }
            print(json.dumps(response), flush=True)
            continue

        if not isinstance(request, dict):
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request"},
                "id": None,
            }
            print(json.dumps(response), flush=True)
            continue

        response = _handle_request(request)
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    serve()
