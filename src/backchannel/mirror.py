import os
from pathlib import Path
import sys
import tempfile
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import transcript
from .models import TranscriptError
from .render import render


def zone(name):
    if not name or name == "local":
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise TranscriptError(f"unknown timezone {name!r}") from error


def snapshot(config, tz=None):
    session = transcript.newest_session(config.agent, config.workspace)
    messages = transcript.read(config.agent, session)
    body = render(messages, config.you_label, config.agent_label, tz)
    return session, body


def write_atomic(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".transcript-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as target:
            target.write(body)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def run(config, once=False, log=sys.stderr):
    tz = zone(config.timezone)
    target = config.transcript_file
    previous = None
    while True:
        try:
            session, body = snapshot(config, tz)
            signature = (session, session.stat().st_mtime_ns)
            if signature != previous:
                write_atomic(target, body)
                previous = signature
        except (TranscriptError, OSError) as error:
            log.write(f"mirror: {error}\n")
            log.flush()
        if once:
            return 0
        time.sleep(config.poll_seconds)
