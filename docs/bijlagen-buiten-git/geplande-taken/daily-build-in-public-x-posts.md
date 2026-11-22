---
name: daily-build-in-public-x-posts
description: Daily build-in-public X post drafts for Daniel (Revaleur + CrossList EU)
---

Generate 2-4 draft "build in public" posts for X (Twitter) for Daniel, ready to copy-paste as-is.

Context: Daniel runs two things — (1) Revaleur, a secondhand luxury clothing reselling store with 700+ five-star reviews, and (2) CrossList EU, a cross-listing SaaS tool he's actively building (backend: FastAPI/Supabase, frontend: frontend/app.html, Chrome extension automation for Marktplaats/2dehands/Vinted, blog/content pipeline, etc.) — the repo lives at the crosslist-eu project.

THIS IS A BRAND NEW X ACCOUNT — CONTINUITY MATTERS.
This is not a one-off — it's a running, chronological build-in-public story. Treat each day as the next entry in a timeline, not an isolated random snapshot. Before writing anything:

1. Check for a history file at `~/.claude/buildinpublic-history.md` (create it if it doesn't exist).
2. Read it to see what's already been posted (dates + short summary of each prior post) so you know exactly where the story left off.
3. Decide what "day" of the story this is:
   - If the file is empty/missing or has fewer than ~3 entries: this is the VERY START. Posts should introduce who Daniel is and why he's building CrossList EU — coming from running Revaleur (secondhand luxury reselling, 700+ five-star reviews) and getting fed up with manually copy-pasting listings across Marktplaats/2dehands/Vinted/eBay/Shopify, so he started building a tool to do it for him. This origin story can spread across the first few days (don't cram it all into day 1) — e.g. day 1 could be "who I am + the problem", day 2 "why I decided to just build it myself", day 3 first real screenshot/feature, etc. Keep it human and specific to Revaleur, not generic startup-speak.
   - If there's already history: continue FORWARD from there. Don't repeat the origin story. Pull up real git commit history (see step below) and post about things roughly IN THE ORDER they actually happened/were built — i.e. don't randomly grab a bugfix from 3 days ago if there's a more recent one; follow the actual chronological build order like a devlog, so the account reads as a coherent progression over time (early bugs → early features → later refinements), matching what a real person would post as they went.
4. Gather raw material: run `git log --oneline --since="7 days ago"` and `git log -p --since="7 days ago" -- backend/ frontend/ extension/ scripts/` in the crosslist-eu repo. Cross-reference commit dates against what's already in the history file so you post about NEW things each day, in roughly the order they were built, rather than the same recent window every time.
5. If Daniel has given extra input that day (a note, an anecdote about Revaleur, a customer message, a shipping/packing/sourcing story), fold it in — this is exactly the reselling-life texture the account needs, and it doesn't have to tie to git history at all.
6. After generating the day's posts, APPEND a new entry to `~/.claude/buildinpublic-history.md` with today's date and a one-line summary of each post's topic (not the full text, just enough for future runs to know what's been covered and avoid repeats).

FORMATTING — matters as much as content:
- Write like a real person typing on their phone. Use line breaks between sentences/thoughts liberally — most posts should have blank lines between 2-4 short chunks rather than one dense paragraph.
- Vary post LENGTH a lot: some a single one-line sentence, some 2-3 short lines, some longer multi-line posts (4-8 short chunks). Don't make every post the same length — that's the #1 tell of AI-generated content.
- Lowercase-friendly, imperfect grammar is fine, no em-dash spam, no "not just X, but Y" AI-tells, no hashtags, no corporate voice, no neat 3-part parallel structure.
- Occasionally a post is just a funny one-liner or meme-ish observation with zero lesson attached.

TONE VARIETY — vary registers across the batch, don't make every post the same voice:
- Most days should include AT LEAST ONE longer, more informative/substantive post (6-12 lines) that reads like a real mini-devlog entry: explains what was actually built/fixed, why it mattered, and what he learned — written clearly and a bit more polished than the meme posts, like he's actually trying to teach the reader something. Still human and first-person, still not corporate-sounding, but noticeably more composed/professional than the throwaway one-liners.
- Balance that against the very casual/meme/one-liner posts — the batch as a whole should span a spectrum from "quick lowercase thought while packing a box" to "here's an actual detailed breakdown of a bug and the fix," rather than every post sitting in the same casual register.
- Not every post needs a punchline or a "lesson" — some can just be a straightforward, slightly more professional update on progress.

CONTENT VARIETY — draw from all of these, weighted toward whatever fits the current point in the story:
- Actual reselling stories/struggles from running Revaleur (sourcing, pricing calls, dealing with buyers, slow weeks, an item that sat for months then sold, negotiating, shipping/packing annoyances, the emotional ups and downs of solo reselling)
- New features/fixes shipped in CrossList EU, told in the order they really happened — this is where the longer informative devlog-style posts usually fit best
- Customer feedback moments (a user confused about something, a happy user, a weird bug report)
- Pure meme/lol lines — founder life or reselling life, no strategic point needed
- Framework to mix from (not a checklist — don't force all of them every day): outcomes (rare, always with context), lessons (must include the actual surprise), live thinking (a real undecided question), contrarian takes, process posts, decision posts (real tradeoff + reasoning), surprising moments, small human/lol moments

Rules:
- Across the week, Revaleur reselling-life content must show up regularly, not just CrossList EU updates — hard requirement.
- Across the week, vary tone registers (see TONE VARIETY above) — don't let every post default to the same casual one-liner voice.
- Don't fabricate specific numbers/stats not grounded in real data (don't invent "$5k MRR"). Small plausible human texture (a customer's phrasing, a mundane detail) is fine; hard factual/financial claims are not.

Output format: just the 2-4 draft posts, numbered, preserving intended line breaks exactly (use real blank lines between chunks within a post) so Daniel can paste them straight into X. Keep commentary minimal — this is a quick daily drop, not a report. End by confirming the history file was updated.