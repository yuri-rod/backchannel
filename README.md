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

`bin/backchannel` runs straight from the clone. If you would rather have it on
your PATH, `pipx install .` (or `pip install .`) gives you a `backchannel`
command that works the same from anywhere.

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

## Synthetic example

`examples/codex-session.jsonl` contains a fictitious Codex transcript with two messages.
Render it without reading your real agent history or using a tunnel:

```sh
demo_dir="$(mktemp -d)"
cat > "$demo_dir/config.toml" <<EOF
[bridge]
agent = "codex"
workspace = "$(pwd)/examples/codex-session.jsonl"
title = "Backchannel demo"

[server]
host = "127.0.0.1"
port = 8687
share_root = "$demo_dir/share"
token_file = "$demo_dir/token"
EOF

./bin/backchannel --config "$demo_dir/config.toml" mirror --once
cat "$demo_dir/share/transcript.txt"
```

To view the result locally, start `./bin/backchannel --config "$demo_dir/config.toml" serve` in another terminal, run `./bin/backchannel --config "$demo_dir/config.toml" token`, then open `http://127.0.0.1:8687/?k=<token>` in your browser. The temporary directory contains the demo transcript and token.

## Operating Backchannel

Keep the server bound to `127.0.0.1`. Start one `serve` process and one `mirror` process with the same config; `serve` handles the browser and inbox, while `mirror` refreshes the transcript. For mobile access, read [SECURITY.md](SECURITY.md) before exposing the local port through a tunnel, then use `backchannel url` to print the tokenized link.

For a supervised service, follow the platform-specific steps in [templates/README.md](templates/README.md). Both templates restart on failure and limit rapid retries. Keep their logs visible when troubleshooting, since a bad config stops startup and a missing session is logged while the mirror keeps polling.

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
