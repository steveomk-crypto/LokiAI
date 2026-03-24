from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.x_state import DRAFT_DIR, POST_LOG, QUEUE_DIR, RUNTIME_LOG, ensure_x_layout, get_x_state, save_x_state

WORKSPACE = Path('/home/lokiai/.openclaw/workspace')
LATEST_POST = WORKSPACE / 'x_posts' / 'post_latest.txt'
LEGACY_POST_GLOB = 'post_*.txt'


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _latest_legacy_post() -> Path | None:
    posts_dir = WORKSPACE / 'x_posts'
    files = [p for p in posts_dir.glob(LEGACY_POST_GLOB) if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8').strip()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def _append_post_log(entry: dict[str, Any]) -> None:
    ensure_x_layout()
    try:
        records = json.loads(POST_LOG.read_text(encoding='utf-8')) if POST_LOG.exists() else []
    except Exception:
        records = []
    if not isinstance(records, list):
        records = []
    records.append(entry)
    _write_json(POST_LOG, records)


def generate_draft(post_class: str = 'build_in_public') -> dict[str, Any]:
    ensure_x_layout()
    source = _latest_legacy_post()
    if not source:
        raise FileNotFoundError('No source post_*.txt found in x_posts/')
    text = _read_text(source)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    draft_path = DRAFT_DIR / f'{stamp}_{post_class}.txt'
    draft_path.write_text(text + '\n', encoding='utf-8')
    state = get_x_state()
    state['lastDraftAt'] = _utc_now()
    state['lastResult'] = f'draft:{draft_path.name}'
    save_x_state(state)
    return {'message': 'Draft generated', 'draft_path': str(draft_path), 'post_class': post_class}


def queue_latest_draft() -> dict[str, Any]:
    ensure_x_layout()
    drafts = sorted(DRAFT_DIR.glob('*.txt'))
    if not drafts:
        raise FileNotFoundError('No drafts available in x_posts/drafts/')
    source = drafts[-1]
    queue_path = QUEUE_DIR / source.name
    queue_path.write_text(_read_text(source) + '\n', encoding='utf-8')
    state = get_x_state()
    state['lastResult'] = f'queued:{queue_path.name}'
    save_x_state(state)
    return {'message': 'Draft queued', 'queue_path': str(queue_path)}


def post_latest_queue() -> dict[str, Any]:
    ensure_x_layout()
    queued = sorted(QUEUE_DIR.glob('*.txt'))
    if not queued:
        raise FileNotFoundError('No queued X posts available')
    source = queued[-1]
    LATEST_POST.write_text(_read_text(source) + '\n', encoding='utf-8')
    stamp = _utc_now()
    _append_post_log({
        'timestamp': stamp,
        'queued_file': str(source),
        'text_preview': _read_text(source)[:140],
        'status': 'ready_for_post',
    })
    state = get_x_state()
    state['lastPostAt'] = stamp
    state['lastResult'] = f'post_now:{source.name}'
    save_x_state(state)
    return {'message': 'Queued post prepared as latest post target', 'post_file': str(LATEST_POST), 'source_queue': str(source)}


def inspect_x() -> dict[str, Any]:
    ensure_x_layout()
    state = get_x_state()
    drafts = sorted([p.name for p in DRAFT_DIR.glob('*.txt')])[-5:]
    queued = sorted([p.name for p in QUEUE_DIR.glob('*.txt')])[-5:]
    return {
        'state': state,
        'recentDrafts': drafts,
        'recentQueue': queued,
        'postLog': str(POST_LOG),
        'runtimeLog': str(RUNTIME_LOG),
    }
