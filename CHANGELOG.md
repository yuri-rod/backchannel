# Changelog

## 0.1.2 - 2026-10-28

- Parse transcript records one at a time instead of keeping a second copy of the
  entire decoded transcript in memory.
- Skip non-object JSON records in Claude Code transcripts, preserving later valid
  messages instead of crashing the mirror.

## 0.1.1

- Limit Codex session discovery to transcripts whose workspace matches the
  requested project, while preserving explicit transcript paths.
- Reserve upload capacity across concurrent requests and publish completed
  uploads without overwriting existing inbox files. Conflicting names return
  HTTP 409, and failed uploads remove their temporary files.
- Return HTTP 404 for non-ASCII invalid tokens and a nonzero exit status when
  a one-shot mirror fails.
- Add a synthetic Codex transcript and a reproducible localhost workflow.
  Document upload limits, redaction scope and filesystem requirements.
- Restrict CI token permissions to repository reads.
