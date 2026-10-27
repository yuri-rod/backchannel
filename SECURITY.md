# Security

Backchannel serves a coding-session transcript and accepts files for an agent
running with your permissions. Review both the session contents and the
agent's inbox instructions before enabling remote access.

## Shared token

Every page, transcript, and upload request requires one token, generated with
`secrets.token_urlsafe(18)` and compared with `secrets.compare_digest`.
Missing or wrong tokens receive HTTP 404 after a short delay. The delay is not
network rate limiting.

Anyone holding the URL can read the transcript and submit input. There are no
separate users, sessions, or second factor. Keep the link private. To rotate
the token, delete its file and restart the server; existing links stop working.

The token travels in the query string, so it appears in browser history and
may appear in tunnel logs. Responses send `Cache-Control: no-store` and
`Referrer-Policy: no-referrer`. The page also includes a referrer meta tag and a
Content Security Policy restricting requests to its own origin. These headers
do not remove the URL from history or tunnel logs.

## Session selection and filtering

Codex workspace discovery checks the metadata `cwd` before choosing from the
global sessions directory. Missing, malformed, or oversized metadata does not
match. An explicit rollout file or directory remains an explicit selection.
Use a file path to pin one session rather than following the newest match.

The Claude Code parser drops sidechain and metadata records, non-text content
blocks such as thinking and tool results, and these harness tags:

- `system-reminder`
- `command-name`, `command-message`, `command-args`
- `local-command-stdout`, `local-command-caveat`
- `bash-input`, `bash-stdout`, `bash-stderr`

The Codex parser keeps supported user-message events and assistant prose in
`commentary` and `final_answer` phases. Other records are excluded.
[Claude redaction tests](tests/test_claude_code.py) and
[Codex selection and parsing tests](tests/test_codex.py) use synthetic records.
Add equivalent tests when changing or adding an adapter.

Filtering does not remove credentials or other sensitive information typed
into an ordinary message. Do not mirror sessions containing information you
cannot share with every holder of the URL.

## Uploads and agent permissions

`POST /send` requires the token, an ASCII filename without separators or a
leading dot, and a positive `Content-Length` within the configured size limit.
In-flight uploads reserve inbox capacity before reading their bodies. Requests
have a 30-second socket timeout and uploads have a five-minute deadline.

Bodies stream to private `0600` temporary files and become visible under the
requested name only after completion. Truncated uploads are removed. Existing
names return HTTP 409 without replacing pending files; choose a different name
or move processed files out of the inbox. Atomic publication requires a
filesystem that supports hard links. Run only one server process per inbox.

The server stores input; the inbox watcher tells the agent how to act on it.
An uploaded file can contain prompt injection. Restrict the agent's filesystem
and tool permissions to what that session needs. HTTP validation cannot control
what the agent does after reading an accepted file.

## Network binding

The default is `127.0.0.1`. Keep it there. The server speaks plain HTTP and is
intended to sit behind a tunnel that terminates TLS for remote access. Binding
to `0.0.0.0` exposes token-protected traffic in cleartext on the LAN and is
unsupported.

## Reporting

Use GitHub issues for non-sensitive reports. Report vulnerabilities through
this repository's private security advisory form. Do not include real tokens,
private transcripts, or customer data in a public report.
