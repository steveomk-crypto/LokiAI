"""Shared helpers to read operational state flags for downstream channels."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

OPS_STATE_PATH = Path("/data/.openclaw/workspace/ops_state.yaml")

DEFAULT_STATE: Dict[str, Any] = {
    "channels": {
        "market_radar": {
            "enabled": True,
            "mode": "draft",  # draft | auto | manual
            "targets": ["queue"]
        },
        "x_autoposter": {
            "enabled": False,
            "mode": "manual",
            "last_change": None
        },
        "telegram_sender": {
            "enabled": False,
            "mode": "manual"
        }
    },
    "draft_only": True,
    "queue": {
        "packet_dir": "/data/.openclaw/workspace/queues/market_radar",
        "retention_minutes": 120
    },
    "notes": "Set channel.enabled true + mode=auto only after manual approval."
}


def _strip_comments(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)  # type: ignore[arg-type]
        else:
            result[key] = value
    return result


def load_ops_state() -> Dict[str, Any]:
    if not OPS_STATE_PATH.exists():
        return deepcopy(DEFAULT_STATE)

    raw_text = OPS_STATE_PATH.read_text(encoding="utf-8").strip()
    if not raw_text:
        return deepcopy(DEFAULT_STATE)

    data: Dict[str, Any] = {}
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(raw_text) or {}
    except ModuleNotFoundError:
        sanitized = _strip_comments(raw_text)
        if sanitized:
            data = json.loads(sanitized)
    except Exception:
        # Fallback to JSON parsing if YAML parsing failed for any other reason
        sanitized = _strip_comments(raw_text)
        if sanitized:
            data = json.loads(sanitized)

    if not isinstance(data, dict):
        data = {}

    merged = _deep_merge(DEFAULT_STATE, data)
    return merged


def enabled_channel_names(state: Dict[str, Any], include_draft: bool = True) -> list[str]:
    names: list[str] = []
    for channel, cfg in state.get("channels", {}).items():
        if not isinstance(cfg, dict):
            continue
        if not cfg.get("enabled"):
            continue
        mode = (cfg.get("mode") or "").lower()
        if not include_draft and mode == "draft":
            continue
        names.append(channel)
    return names
