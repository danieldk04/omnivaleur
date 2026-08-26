# Omnivaleur — project instructions

This file is repo-local and checked into git, so it loads for every Claude
Code session opened against this repo — on any of Daniel's machines or
Anthropic accounts. That makes it the right place for anything that must
never depend on which account happens to be running.

## Before touching anything people/business/decision-related

Read [docs/team-notes.md](docs/team-notes.md) first. It's an append-only log
of team, partnership, and business-decision context — who's involved, what
was agreed, why. Unlike `~/.claude` memory (which is per-account and does
not follow Daniel between logins), this file travels with the repo, so it's
the only place that guarantees a session on a *different* account isn't
missing context a session on another account already has.

When you make or learn a decision of that kind, append a dated entry to
`docs/team-notes.md` and push it — the same way a code change gets pushed.
Do not let it live only in memory or only in chat.
