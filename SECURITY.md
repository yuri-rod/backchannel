# Security

Read this before you point a tunnel at the server. The threat model is unusual:
the page publishes a transcript of an AI coding session, and the write side
hands files to an agent that is running with your permissions.

## What protects the URL

One token. `secrets.token_urlsafe(18)` is 144 bits, compared with
`secrets.compare_digest`, and every route refuses without it. A wrong token gets
the same `404` as a wrong path, after a short pause, so the URL gives away
nothing about whether it is a live instance.

There is no session, no login and no second factor. **Anyone holding the URL has
everything.** Treat it like an SSH key, not like a password.

## The token is in the query string

That is a real trade-off, taken so the link works from a phone lock screen with
no typing. The consequences:

- It lands in the browser history of every device you open it on.
- It lands in the logs of whatever tunnel you use.
- It would leak through a `Referer` header on any outbound link.

Mitigations in the code: `Referrer-Policy: no-referrer` and a `<meta>` referrer
tag, `Cache-Control: no-store` on every response, and the token is read from
`location.search` rather than written into the page body. A `Content-Security-
Policy` blocks outbound requests to anything but the server's own origin.

To rotate: delete the token file and restart. Every old link dies.

## The transcript is the sensitive part

`mirror` renders the agent's own session file. Before anything reaches the page
it drops, in this order:

- Records marked `isSidechain` or `isMeta` (subagent traffic, harness bookkeeping)
- Every content block that is not prose: `thinking`, `tool_use`, `tool_result`
- `<system-reminder>...</system-reminder>` blocks
- `<command-name>`, `<command-message>`, `<command-args>`,
  `<local-command-stdout>`, `<local-command-caveat>`, `<bash-input>`,
  `<bash-stdout>`, `<bash-stderr>`

`tests/test_claude_code.py::RedactionTests` pins all of it. If you add an
adapter, add the equivalent tests before you run it against anything real.

This still leaves whatever you and the agent said to each other in plain prose.
If you paste a credential into a chat, the mirror will publish it. **Do not run
this against a session that handles material you would not put on a public URL.**

## The write side

`POST /send` writes into an inbox directory that your agent is told to read and
act on. That is, by design, remote input to a process with your shell. The
server constrains it to: a token, a filename matching
`^[A-Za-z0-9][A-Za-z0-9._ -]{0,126}[A-Za-z0-9]$` (no traversal, no dotfiles), a
size ceiling, a cap on pending files, a 30-second socket timeout and a 5-minute
upload deadline. Bodies stream to a `0600` temporary file and are renamed into
place only once complete, so a truncated upload never becomes a visible file.

What the server cannot constrain is what the agent does with the content. The
inbox is untrusted input reaching a tool-using agent: prompt injection in an
uploaded file is a live risk, and no amount of HTTP validation fixes it. Keep
the agent's own permissions tight.

## Binding

`host` defaults to `127.0.0.1` and should stay there. The server speaks plain
HTTP with no TLS and no rate limiting on the network path. It is meant to sit
behind a tunnel (ngrok, Cloudflare Tunnel, Tailscale Funnel) that terminates TLS
for it. Binding it to `0.0.0.0` puts an unauthenticated-by-network,
token-only, cleartext service on your LAN. Unsupported.

## Reporting

Open a GitHub issue for anything non-sensitive. For a vulnerability that should
not be public, use GitHub's private security advisory form on this repository.
