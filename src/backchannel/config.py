from dataclasses import dataclass, fields
import os
from pathlib import Path
import tomllib

DEFAULT_CONFIG_PATH = Path("~/.config/backchannel/config.toml")
ENV_PREFIX = "BACKCHANNEL_"

# Every field maps to <section>.<name> in the TOML file and to
# BACKCHANNEL_<NAME> in the environment. Env wins, so a token or a port can be
# overridden by the launcher without editing the file.
SECTIONS = {
    "agent": "bridge",
    "workspace": "bridge",
    "title": "bridge",
    "you_label": "bridge",
    "agent_label": "bridge",
    "host": "server",
    "port": "server",
    "share_root": "server",
    "token_file": "server",
    "max_upload_bytes": "server",
    "max_pending_uploads": "server",
    "poll_seconds": "mirror",
    "timezone": "mirror",
}

PATH_FIELDS = {"workspace", "share_root", "token_file"}


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    agent: str = "claude-code"
    workspace: Path = Path.cwd()
    title: str = "Backchannel"
    you_label: str = "YOU"
    agent_label: str = "AGENT"

    host: str = "127.0.0.1"
    port: int = 8686
    share_root: Path = Path("~/.backchannel/share")
    token_file: Path = Path("~/.backchannel/token")
    max_upload_bytes: int = 100 * 1024 * 1024
    max_pending_uploads: int = 20

    poll_seconds: float = 2.0
    timezone: str = "local"

    @property
    def inbox(self):
        return self.share_root / "inbox"

    @property
    def transcript_file(self):
        return self.share_root / "transcript.txt"


def load(path=None, environ=None):
    environ = os.environ if environ is None else environ
    path = Path(path) if path else Path(environ.get(f"{ENV_PREFIX}CONFIG", DEFAULT_CONFIG_PATH))
    values = _from_file(path.expanduser())
    values.update(_from_env(environ))
    return _build(values)


def _from_file(path):
    if not path.exists():
        return {}
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"cannot read {path}: {error}") from error
    values = {}
    for name, section in SECTIONS.items():
        table = document.get(section)
        if isinstance(table, dict) and name in table:
            values[name] = table[name]
    unknown = _unknown_keys(document)
    if unknown:
        raise ConfigError(f"unknown settings in {path}: {', '.join(sorted(unknown))}")
    return values


def _unknown_keys(document):
    known = {(section, name) for name, section in SECTIONS.items()}
    found = set()
    for section, table in document.items():
        if not isinstance(table, dict):
            found.add(section)
            continue
        for name in table:
            if (section, name) not in known:
                found.add(f"{section}.{name}")
    return found


def _from_env(environ):
    values = {}
    for name in SECTIONS:
        raw = environ.get(f"{ENV_PREFIX}{name.upper()}")
        if raw is not None:
            values[name] = raw
    return values


def _build(values):
    types = {field.name: field.type for field in fields(Config)}
    coerced = {}
    for name, raw in values.items():
        coerced[name] = _coerce(name, raw, types[name])
    config = Config(**coerced)
    if config.port < 1 or config.port > 65535:
        raise ConfigError(f"port out of range: {config.port}")
    if config.poll_seconds <= 0:
        raise ConfigError("poll_seconds must be positive")
    if config.max_upload_bytes < 1:
        raise ConfigError("max_upload_bytes must be positive")
    if config.max_pending_uploads < 1:
        raise ConfigError("max_pending_uploads must be positive")
    if not config.you_label.strip() or not config.agent_label.strip():
        raise ConfigError("speaker labels cannot be blank")
    return config


def _coerce(name, raw, annotation):
    if name in PATH_FIELDS:
        return Path(raw).expanduser()
    try:
        if annotation is int or annotation == "int":
            return int(raw)
        if annotation is float or annotation == "float":
            return float(raw)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{name} is not a number: {raw!r}") from error
    return str(raw)
