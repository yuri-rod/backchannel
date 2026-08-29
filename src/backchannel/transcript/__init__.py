from ..models import TranscriptError
from . import claude_code, codex

READERS = {
    claude_code.NAME: claude_code,
    codex.NAME: codex,
}


def reader_for(agent):
    try:
        return READERS[agent]
    except KeyError:
        known = ", ".join(sorted(READERS))
        raise TranscriptError(f"unknown agent {agent!r}, expected one of: {known}") from None


def newest_session(agent, workspace):
    reader = reader_for(agent)
    sessions = [path for path in reader.sessions(workspace) if path.is_file()]
    if not sessions:
        raise TranscriptError(f"no {agent} session found for {workspace}")
    return max(sessions, key=lambda path: path.stat().st_mtime)


def read(agent, path):
    return reader_for(agent).parse(path)
