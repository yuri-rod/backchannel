from datetime import datetime

from .models import YOU

NO_CLOCK = "--:--"


def render(messages, you_label="YOU", agent_label="AGENT", tz=None):
    blocks = []
    for message in messages:
        if not message.text:
            continue
        label = you_label if message.speaker == YOU else agent_label
        blocks.append(f"### {label}  {clock(message.timestamp, tz)}\n\n{message.text}\n")
    return "\n".join(blocks)


def clock(timestamp, tz=None):
    if not isinstance(timestamp, str):
        return NO_CLOCK
    try:
        moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return NO_CLOCK
    return moment.astimezone(tz).strftime("%H:%M")
