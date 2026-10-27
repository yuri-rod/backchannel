# backchannel

Read a local coding agent's conversation and send it messages or files from a
browser, using a token-protected Python server.

Use it to check a long-running Claude Code or Codex session from your phone.
The mirror renders the selected session into a transcript; the server delivers
that transcript and accepts uploads into an inbox. An agent-side watcher must
read the inbox before the agent can act on a message.

Python 3.11 or newer. No runtime dependencies.

## Try it locally

This example uses the included synthetic conversation. It needs neither a real
agent session nor a tunnel.

```sh
git clone https://github.com/yuri-rod/backchannel
cd backchannel
demo_dir="$(mktemp -d)"
cat > "$demo_dir/config.toml" <<EOF_CONFIG
[bridge]
agent = "codex"
workspace = "$(pwd)/examples/codex-session.jsonl"
title = "Backchannel demo"

[server]
host = "127.0.0.1"
port = 8687
share_root = "$demo_dir/share"
token_file = "$demo_dir/token"

[mirror]
timezone = "UTC"
EOF_CONFIG

./bin/backchannel --config "$demo_dir/config.toml" mirror --once
cat "$demo_dir/share/transcript.txt"
```

Output:

```text
### YOU  00:00

Draft a backup checklist for a sample service.

### AGENT  00:00

Record the last successful backup, retain seven daily copies, and verify one restore.
```

Start the demo server in the same terminal:

```sh
./bin/backchannel --config "$demo_dir/config.toml" token
./bin/backchannel --config "$demo_dir/config.toml" serve
```

Open `http://127.0.0.1:8687/?k=<printed-token>`. Send a message in the composer
and inspect the resulting `pasted-*.txt` file in the temporary `share/inbox`
directory. This demo has no agent watcher, so it records the message without
executing it. Stop the server with Ctrl-C.

`bin/backchannel` runs directly from the clone. To install the command on your
PATH instead, use `pipx install .` or `python3 -m pip install .` inside a virtual
environment. The installed command is `backchannel`.

## Connect a session

Copy [config.example.toml](config.example.toml) to
`~/.config/backchannel/config.toml` and set `bridge.agent` and
`bridge.workspace`. Start one `backchannel serve` process and one
`backchannel mirror` process with the same config. The mirror refreshes the
transcript while the server handles the browser and inbox.

| Adapter | Session selection |
| --- | --- |
| `claude-code` | A directory containing JSONL sessions, or the Claude project directory derived from the workspace path |
| `codex` | An explicit rollout file, a directory containing `rollout-*.jsonl`, or sessions whose metadata `cwd` matches the workspace |

The newest matching session by modification time wins. Codex discovery skips
missing, invalid, or oversized metadata headers rather than selecting an
unrelated workspace. Use an explicit rollout file to pin one conversation.

Configuration comes from `~/.config/backchannel/config.toml`, `--config`, or
`BACKCHANNEL_CONFIG`. Individual `BACKCHANNEL_<SETTING>` environment variables
override file values. Unknown configuration keys are errors.

`mirror --once` returns a nonzero exit status if it cannot read or write the
snapshot. The continuous mirror logs missing-session and filesystem errors and
keeps polling. Service templates and installation commands are in
[templates/README.md](templates/README.md).

## Mobile access and replies

Keep the server on `127.0.0.1`. For mobile access, read
[SECURITY.md](SECURITY.md), then forward the local port through a TLS tunnel.
For example, `ngrok http 8686` followed by `backchannel url` prints the shared
link. With another tunnel, append `?k=<token>` to its URL; `backchannel token`
prints the token.

Anyone holding that link can read the transcript and write to the inbox.
Tokens appear in browser history and may appear in tunnel logs. Keep them out
of issue reports, screenshots, and commits.

[agent/watch-inbox.md](agent/watch-inbox.md) contains a watcher instruction.
For Claude Code, copy it to the project's `.claude/commands/` directory and run
`/watch-inbox`. For Codex, provide its body as an instruction. Inbox contents are
remote input to an agent with your permissions; review the watcher before
using it. Move processed files out of the inbox to free capacity.

## Engineering details

- [server.py](src/backchannel/server.py) authenticates both reads and uploads,
  validates filenames and body sizes, and reserves inbox capacity before
  reading an upload. Completed files are published atomically with mode `0600`.
  Existing names return HTTP 409 instead of replacing pending input. Incomplete
  uploads are removed.
- [mirror.py](src/backchannel/mirror.py) writes transcripts through a private
  temporary file and atomic replacement, so readers see complete snapshots.
- [transcript/](src/backchannel/transcript/) separates session discovery from
  parsing. Adapters keep prose while excluding tool output and reasoning;
  Claude's adapter also strips known harness tags. This filtering does not
  remove secrets someone types into a normal message.

The server uses HTTP, binds to loopback by default, and has one shared token.
It is not a multi-user service. Upload limits are per server process; run one
server for each inbox. The inbox filesystem must support hard links for atomic
publication without replacement.

## Development

```sh
make test
uvx --from ruff==0.16.5 ruff check src tests bin/backchannel README.md
uvx --from ruff==0.16.5 ruff format --check src tests bin/backchannel README.md
```

`make lint` runs the same checks when Ruff is on PATH. CI tests Python 3.11,
3.12, and 3.13 on macOS and Linux. Tests use temporary directories, synthetic
transcripts, and loopback servers on ephemeral ports.

Start with [test_server.py](tests/test_server.py) for authentication, traversal,
capacity, timeout, and filename-conflict coverage;
[test_codex.py](tests/test_codex.py) for workspace isolation; and
[test_mirror.py](tests/test_mirror.py) for snapshot behavior. New adapters expose
`sessions(workspace)` and `parse(path)` and register in
[transcript/__init__.py](src/backchannel/transcript/__init__.py). Include
synthetic selection and redaction tests with adapter changes.

MIT. See [LICENSE](LICENSE).
