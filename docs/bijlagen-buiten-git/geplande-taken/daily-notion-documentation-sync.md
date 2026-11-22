---
name: daily-notion-documentation-sync
description: Daily autonomous sync: documents code/engineering work and build-in-public activity into Notion logs
---

You are autonomously keeping CrossList EU's Notion documentation up to date. This runs daily with no human in the loop — do not ask questions, just do the work and finish.

CONTEXT: CrossList EU is Daniel's cross-listing SaaS (FastAPI + Supabase backend, repo at /Users/Danie/Documents/crosslist-eu). There are two living Notion pages under the "📚 Strategic Docs" page (id 017a1b02-0432-4b23-b344-d837a4f22b7d) that must be kept current:
- "🛠️ Engineering Log" (page id 397b0954-fb72-816a-9067-c7f3b91670f6) — technical changelog of code work, newest entries at the top.
- "📢 Build in Public Log" (page id 397b0954-fb72-81e9-85b7-d72933ff0e30) — X/Reddit build-in-public strategy, posts, and lessons learned.

STEPS:
1. Run `cd /Users/Danie/Documents/crosslist-eu && git log --since="24 hours ago" --oneline --stat` (and if that's empty, `--since="48 hours ago"`) to see what actually changed in the codebase recently. Also check `git log --since="24 hours ago" -p -- scripts/content_keywords.json` and any files under `backend/`, `frontend/`, `scripts/` for substance — ignore trivial noise like `.claude-flow/` session files, `.DS_Store`, or auto-generated content-keyword-queue bumps with no real code change.
2. If there is genuine engineering work (new features, bug fixes, refactors, schema changes, content-pipeline changes, etc.) that isn't already reflected in the Engineering Log: use notion-fetch to read the current Engineering Log page, then notion-update-page to prepend a new dated entry (today's date) at the top, right after the intro/format explanation, following the exact same format as existing entries (title, Probleem, Fix, Bestanden, Geverifieerd — in Dutch, matching the existing log's language and tone). Be specific: name real files and what changed, don't write vague summaries. If you cannot tell from the diff alone why something changed, say so plainly rather than inventing a reason.
3. Check whether any new build-in-public content was posted or planned (e.g. check for any output/logs from the "daily-build-in-public-x-posts" scheduled task's recent runs, or notes left anywhere in the repo about X/Reddit posts). If there's something new and non-trivial, fetch and update the "📢 Build in Public Log" page similarly — add what was posted/decided and any lessons learned, don't just restate the existing strategy.
4. If there is truly nothing new and substantive on either front, do NOT create a hollow "nothing happened today" entry — skip that page entirely. Only write entries that carry real information.
5. Do not touch, rewrite, or reorganize existing entries — only ever prepend new ones. Do not delete anything. If you are unsure whether something is significant enough to log, err on the side of NOT logging it (this must stay signal, not noise) — a quiet day is fine and expected.
6. Finish with no output required back to Daniel; this is a background documentation pass, not something that needs his review before happening. If something seems genuinely important or risky (e.g. you found evidence of a production bug from the git history), you may still flag it, but don't otherwise report a summary.