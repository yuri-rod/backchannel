# backchannel

Talk to a coding agent running on your laptop from your phone, over a tunnel,
through one token-protected URL.

You leave Claude Code or Codex working on your machine. `backchannel` mirrors
that session to a mobile page you can read live, and gives you a box to send
text or files back. Whatever you send lands in an inbox directory the agent
watches, so it picks the message up and answers on its own.

No dependencies. Python standard library only, about 700 lines.

```
  ~/.claude/projects/<project>/*.jsonl      the agent's own session file
                |
                |  mirror: parse, drop harness noise, render
                v
  ~/.backchannel/share/transcript.txt
                |                                   phone
                |  serve: GET /transcript.txt         |
                v                                     |
       127.0.0.1:8686  <---- tunnel (ngrok/etc) <-----+
                ^                                     |
                |  serve: POST /send                  |
                |                                     v
  ~/.backchannel/share/inbox/  ----> the agent's inbox watcher
```

## Quickstart

Needs Python 3.11 or newer and a tunnel of your choice.

```
git clone https://github.com/yuri-rod/backchannel
cd backchannel
mkdir -p ~/.config/backchannel
cp config.example.toml ~/.config/backchannel/config.toml
$EDITOR ~/.config/backchannel/config.toml   # set bridge.workspace

./bin/backchannel serve &
./bin/backchannel mirror &
```

Point a tunnel at port 8686:

```
ngrok http 8686
```

Then print the link and open it on your phone:

```
./bin/backchannel url
```

`url` asks ngrok's local API which tunnel forwards to your port and appends the
token. With another tunnel, build the link yourself:
`https://your-tunnel-host/?k=$(./bin/backchannel token)`.

## Making the agent answer

The page's write side only drops files into the inbox. Something has to watch
that directory and act, and that something is the agent itself.

`agent/watch-inbox.md` is a ready slash command. For Claude Code, copy it into
`.claude/commands/` in the project you are working in and run
`/watch-inbox`. For Codex, paste its body as your first instruction.

The pattern is the same either way: arm a loop on the inbox, and when a file
appears, read it and act without waiting to be told.

## Configuration

`config.example.toml` documents every setting. It is read from
`~/.config/backchannel/config.toml`, or from `--config`, and every value can
be overridden by `BACKCHANNEL_<SETTING>` in the environment.

The two that matter on day one:

| Setting | What it does |
|---|---|
| `bridge.agent` | `claude-code` or `codex` |
| `bridge.workspace` | the project whose session you want mirrored |

An unknown key in the file is an error rather than a silent no-op, so a typo in
`prot = 8686` tells you instead of leaving you on the default port.

## Agent adapters

An adapter is a module under `src/backchannel/transcript/` exposing two
functions:

```python
NAME = "my-agent"

def sessions(workspace):
    """Return candidate session file paths. The newest mtime wins."""

def parse(path):
    """Return a list of Message(speaker, text, timestamp)."""
```

Register it in the `READERS` map in `transcript/__init__.py`. Two ship in the
box:

- **claude-code** reads `~/.claude/projects/<slug>/*.jsonl`, where the slug is
  the workspace path with every non-alphanumeric character replaced by `-`.
- **codex** reads `rollout-*.jsonl` from `~/.codex/sessions`, keeping user
  messages and assistant `commentary` and `final_answer` phases.

If you write an adapter, write its redaction tests too. Read
[SECURITY.md](SECURITY.md) first: the parser is the only thing standing between
a harness-injected system prompt and a public web page.

## Running it as a service

`templates/` has a launchd plist template and a systemd user unit, with the
install commands in `templates/README.md`.

## Security

The URL is public and a single token is all that protects it. The transcript is
filtered but it is still your conversation. The inbox is untrusted input
reaching a tool-using agent.

[SECURITY.md](SECURITY.md) covers the whole model. Read it before you expose
anything.

## Tests

```
make test     # 59 tests, standard library unittest
make lint     # ruff, if you have it
```

## License

MIT. See [LICENSE](LICENSE).
