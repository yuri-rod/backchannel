import json
from pathlib import Path
import re

from ..models import AGENT, YOU, Message, TranscriptError

NAME = "claude-code"
PROJECTS_DIR = Path("~/.claude/projects").expanduser()

SPEAKERS = {"user": YOU, "assistant": AGENT}

# Everything below is stripped before a line can reach the public page. The
# harness injects these blocks into the transcript, and they routinely carry
# system prompts, file contents and command output that were never meant to
# leave the machine.
REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)
HARNESS_TAG = re.compile(
    r"<(command-name|command-message|command-args|local-command-stdout"
    r"|local-command-caveat|bash-input|bash-stdout|bash-stderr)>.*?</\1>",
    re.DOTALL,
)


def sessions(workspace):
    return sorted(project_dir(workspace).glob("*.jsonl"))


def project_dir(workspace):
    workspace = Path(workspace).expanduser()
    if any(workspace.glob("*.jsonl")):
        return workspace
    candidate = PROJECTS_DIR / slug(workspace)
    if not candidate.is_dir():
        raise TranscriptError(
            f"no Claude Code project directory for {workspace} (looked for {candidate})"
        )
    return candidate


def slug(workspace):
    return re.sub(r"[^A-Za-z0-9-]", "-", str(Path(workspace).expanduser()))


def parse(path):
    return [message for message in _messages(_records(path)) if message.text]


def _records(path):
    records = []
    with Path(path).open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                # A live session's last line is often half-written.
                continue
    return records


def _messages(records):
    for record in records:
        if record.get("isSidechain") or record.get("isMeta"):
            continue
        speaker = SPEAKERS.get(record.get("type"))
        if speaker is None:
            continue
        yield Message(speaker, _prose(record.get("message")), record.get("timestamp"))


def _prose(message):
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return redact(content)
    parts = []
    for block in content or []:
        # Only "text" survives: thinking, tool_use and tool_result never ship.
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(redact(block.get("text", "")))
    return "\n\n".join(part for part in parts if part)


def redact(text):
    return HARNESS_TAG.sub("", REMINDER.sub("", text)).strip()
