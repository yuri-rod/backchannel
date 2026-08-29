import json
from pathlib import Path

from ..models import AGENT, YOU, Message

NAME = "codex"
SESSIONS_DIR = Path("~/.codex/sessions").expanduser()

ASSISTANT_PHASES = {"commentary", "final_answer"}


def sessions(workspace):
    # Codex keys rollouts by thread id, not by workspace, so the workspace is
    # only a hint: point `workspace` at a rollout file or at a directory of
    # them, otherwise the whole sessions tree is searched.
    workspace = Path(workspace).expanduser()
    if workspace.is_file():
        return [workspace]
    for root in (workspace, SESSIONS_DIR):
        found = sorted(root.rglob("rollout-*.jsonl")) if root.is_dir() else []
        if found:
            return [path for path in found if not path.is_symlink()]
    return []


def parse(path):
    messages = []
    for record in _records(path):
        message = _message(record)
        if message and message.text:
            messages.append(message)
    return messages


def _records(path):
    records = []
    with Path(path).open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def _message(record):
    payload = record.get("payload")
    timestamp = record.get("timestamp")
    if not isinstance(payload, dict) or not isinstance(timestamp, str):
        return None
    text = _user_text(record, payload)
    if text is not None:
        return Message(YOU, text.strip(), timestamp)
    if (
        payload.get("type") == "message"
        and payload.get("role") == "assistant"
        and payload.get("phase") in ASSISTANT_PHASES
    ):
        return Message(AGENT, (_content_text(payload, "output_text") or "").strip(), timestamp)
    return None


def _user_text(record, payload):
    if record.get("type") != "event_msg" or payload.get("type") != "item_completed":
        return None
    item = payload.get("item")
    if not isinstance(item, dict) or item.get("type") != "UserMessage":
        return None
    return _content_text(item, "text")


def _content_text(payload, part_type):
    content = payload.get("content")
    if not isinstance(content, list):
        return None
    parts = [
        part.get("text")
        for part in content
        if isinstance(part, dict)
        and part.get("type") == part_type
        and isinstance(part.get("text"), str)
    ]
    return "".join(parts) if parts else None
