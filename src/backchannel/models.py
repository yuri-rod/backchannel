from dataclasses import dataclass

YOU = "you"
AGENT = "agent"


@dataclass(frozen=True)
class Message:
    speaker: str  # YOU or AGENT
    text: str
    timestamp: str


class TranscriptError(RuntimeError):
    pass
