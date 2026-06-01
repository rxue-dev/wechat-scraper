"""Checkpoint read/write for resume support."""

import json
from pathlib import Path


STATE_FILE = Path(__file__).parent / "state.json"


def load_state():
    """Load saved checkpoints. Returns dict of chat_name -> checkpoint info."""
    if not STATE_FILE.exists():
        return {}
    with open(STATE_FILE) as f:
        return json.load(f)


def save_state(state):
    """Persist checkpoint state to disk."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_checkpoint(chat_name):
    """Get the last scraped message hash and timestamp for a chat.

    Returns None if no checkpoint exists.
    """
    state = load_state()
    return state.get(chat_name)


def update_checkpoint(chat_name, message_hash, timestamp):
    """Save the most recent message as the resume checkpoint for a chat."""
    state = load_state()
    state[chat_name] = {
        "last_hash": message_hash,
        "last_timestamp": timestamp,
        "updated_at": _now_iso(),
    }
    save_state(state)


def _now_iso():
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=8))).isoformat()
