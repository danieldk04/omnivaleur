# Team & Partnership Notes

Append-only log, newest entry on top. Read this before starting anything that
touches people, roles, deals, or business decisions — it's the one record
that travels with the repo across every Claude Code session and every
Anthropic account, unlike `~/.claude` memory, which is per-account and does
not follow Daniel between machines/logins.

## Working practice — read this first

Any Claude Code session opened in this repo must treat this file (and its
history via `git log docs/team-notes.md`) as authoritative for
team/partnership/business context. When you make or learn a decision of this
kind — roles, access, deals, non-obvious business context — append a dated
entry below and push it, exactly like a code change. Per-account `~/.claude`
memory can still be written on top for fast recall, but never as the only
record: anything here has to survive a switch to a different Claude account
without Daniel repeating himself.

## 2026-08-26 — Monaim joins as 50/50 partner

- Monaim is coming on as a 50/50 partner on **Omnivaleur** specifically —
  not Somnia (his own e-commerce brand, unrelated) and not Revaleur.
  **Revaleur is Daniel's own vintage clothing brand; Omnivaleur is the
  software Daniel originally built to run Revaleur's own cross-listing,**
  later spun out into a standalone SaaS product.
- Structure is deliberately informal for now: no equity/contract yet. Legal
  vastlegging of the 50/50 is postponed on purpose until both sides are happy
  with how the working relationship actually plays out.
- Focus at the start: organic content for Omnivaleur's **Dutch-language**
  socials (TikTok/Instagram) — schema + ideation, editing gets outsourced.
  Also owns exploring a social-DM outreach system (parallel idea to the
  existing cold-email leadgen — see the `leadgen` skill for how that one is
  structured: find → first contact → log). **But right now (pre-50-users),
  the real company-wide priority is dashboard improvements, debugging, and
  gathering user feedback** — Monaim's content/outreach work runs alongside
  that, not instead of it, and doesn't compete with it for resources.
- Suggested role/tasks: **Growth & Content Partner.**
  1. Weekly Dutch content schema for TikTok + Instagram — he floated 3 posts
     + 1 video/week as a first test cadence.
  2. Design + test a social-DM outreach flow for finding NL tweedehands
     sellers on IG/TikTok (VA-run vs. extension vs. manual — undecided).
  3. Track weekly content performance (views, follows, signups attributed)
     — this is what tells us when organic has enough signal to justify ad
     spend, not a fixed date.
- **When to start paid ads: at 50 users** (concrete threshold, set by
  Daniel — not "once conversion is validated" in the abstract anymore).
  - **First phase targets clothing/shoe sellers specifically** — that's what
    the dashboard is built for and where it performs best; don't broaden the
    ad targeting past that niche in phase one.
  - **Creatives:** organic content can double as ad creatives if the quality
    is good enough — no separate production required by default. Monaim may
    also build dedicated landing pages for ad traffic.
  - **Geography: Europe only.** Deliberately stay out of US/UK — competition
    among cross-listing tools is by far the fiercest there.
  - **Competitive positioning:** Channable is the dominant tool most
    marketplace sellers currently use — large, but very poorly rated. Its
    focus is broad marketplace selling in general (including bol.com etc.).
    Omnivaleur's differentiation is staying narrow: **secondhand
    (tweedehands) platforms only**, for now. Don't pitch Omnivaleur as a
    general marketplace tool — that's Channable's ground, and it's already
    lost on reviews.
  - Blogs are **fully automated** already (see `backend/content/quality.py`
    and the daily auto-publish job) — not part of Monaim's remit, mentioned
    only so he doesn't assume it's an open task.
- **Free account:** `backend/services/billing.py` now recognizes a
  `complimentary` subscription status — unlimited access, no
  `stripe_subscription_id` required (see `evaluate_access`). To activate for
  Monaim: he signs up normally at omnivaleur.com with his own email (creates
  the usual 7-day `trialing` row), then Daniel sets that row's `status` to
  `complimentary` in Supabase. **Do not** use `status = active` without a
  `stripe_subscription_id` — that path is intentionally blocked (guards
  against a past bug where it silently granted free access).
- **Notion:** Daniel is giving Monaim full workspace access. No further
  restriction recommended given the 50/50 framing — gate by task assignment,
  not by permissions.
- The original onboarding document (product overview, brand colors/type,
  cijfers) was published as a Claude Artifact on 2026-08-26 and handed to
  Daniel directly in chat — not duplicated here since artifacts aren't repo
  files.
