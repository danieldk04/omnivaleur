# Build in Public — X Post History

## 2026-07-06 (Day 1)
- Post 1: one-liner, starting to post here instead of just complaining in his head
- Post 2: intro/context — runs Revaleur (secondhand designer clothing, 700+ five-star reviews), sets up "the boring part of reselling" as the hook
- Post 3: the actual pain — same listing across Marktplaats/2dehands/Vinted/eBay/Shopify, manual repost/delete/reprice across 5 tabs
- Post 4: funny one-liner — the "five stages of grief" for a listing that won't sell

(Origin story continues: day 2+ should cover deciding to just build CrossList EU himself — do not repeat this day's content.)

## 2026-07-07 (Day 2)
- Post 1: researched Vendoo/List Perfectly first — both US-focused, no real Vinted/Marktplaats support
- Post 2: the tipping point — List Perfectly's "one tab per item" bulk cross-listing crashing the browser on 40 items
- Post 3: Revaleur anecdote — a jacket sat unlisted for ~4 months because relisting everywhere felt like too much friction
- Post 4: process post — started the repo (FastAPI + Supabase + Chrome extension to drive listing flows since no public APIs), open question on scope

## 2026-07-07 (Day 3)
- Post 1: funny one-liner — added the Revaleur logo asset via terminal instead of editor, auto-commit hook never picked it up, homepage badge 404'd
- Post 2: quiet bug — imported items with empty gender field were silently defaulting to "dames jeans"; fixed by parsing gender from title text (heren/dames/men's/women's) before falling back
- Post 3: long devlog — Vinted listing-id auto-detection bug: regex was built around Marktplaats/2dehands's m-prefixed ids, Vinted uses plain digits (/items/9331465721), so jobs stayed stuck "claimed" forever; fixed with a platform-specific regex; lesson on not stretching one platform's id format to a new one
- Post 4: Revaleur anecdote — a coat that sat for weeks finally sold, buyer messaged right after paying that they'd been searching for that exact color for ages

(Day 4+ still has plenty to draw from: relist.py changes, listings.py, crosslist.py, seed_demo_account.py, content pipeline/blog keyword queue, Vinted/Marktplaats/2dehands extension scripts, app.html UI iterations. Note: Day 3 was generated same-calendar-day as Day 2 — confirm with Daniel if the schedule is meant to fire once/day; if so this may indicate a duplicate trigger.)

## 2026-07-08 (Day 4)
- Post 1: funny one-liner — built the "missing data" warning badges, turned it on, own demo inventory lit up with gaps
- Post 2: long devlog — relist price-drop feature (refresh modal + backend `new_price` param): the psychology (10-15% drop + fresh timestamp), and the bug where the discount wasn't persisted to the item's base price so it reverted on the next refresh
- Post 3: process/decision post — mirrored backend's required-fields validation (crosslist.py) into the frontend so missing size/color/etc. shows as a badge before publish instead of a 422 after
- Post 4: Revaleur anecdote — packing orders before checking email, buyer asking for a discount on an already-sold item

(Day 5+ material still untouched: seed_demo_account.py, crosslist.py/items.py core validation, jobs.py, background.js/shared.js, marktplaats.js/tweedehands.js/vinted.js extension scripts, schema.sql, content keyword queue/content-blog.yml pipeline work, launch.json, index.html homepage founder badge follow-up.)

## 2026-07-08 (Day 5)
- Post 1: funny one-liner — built an admin-only "comp this email a free account" endpoint (billing.py), joked about building a SaaS just to have more ways to not charge for it
- Post 2: long devlog — the demo-seed-account permission saga (seed_demo_account.py): started with admin.list_users/admin.create_user assuming service-role access, hit 403s because the deployed key is anon-only, worked around it by creating the account once by hand and hardcoding its id, then hit Supabase RLS blocking a direct subscriptions insert too — ended up leaning on the billing/status endpoint's lazy trial-creation on first login instead
- Post 3: medium devlog — closed the loop on yesterday's frontend validation badges: items.py now catches CrosslistValidationError from the service layer and returns a proper 422 with a missing_fields list instead of the request just blowing up, so the badges have structured data to point at
- Post 4: Revaleur anecdote — buyer asked "best price?" on an item already priced under recent comps, said no, they bought it at asking price 10 minutes later anyway

(Day 5 was generated same-calendar-day as Day 4 — second fire on 2026-07-08, likely the same duplicate-trigger issue noted for Day 2/3. Continued forward with fresh material rather than repeating.)

## 2026-07-09 (Day 6)
- Post 1: funny one-liner — ripping JS out of a hamburger menu felt more satisfying than any real feature this week
- Post 2: long devlog — replaced the JS-based mobile nav (toggleMenu/closeMenu, classList.toggle) duplicated across privacy/terms/marketplaces/index.html with a single CSS-only checkbox-hack version (.nav-toggle-cb + :checked ~ .nav-panel); motivated by the per-page JS copies drifting out of sync
- Post 3: medium devlog — broadened needs_dutch_translation() in the content pipeline from "only nl/be-nl pages mentioning marktplaats/2dehands" to unconditionally True (every article gets an NL companion); wrote a one-off backfill script (scripts/backfill_nl_translations.py) to retroactively generate NL companions for already-published EN pages that predated the change
- Post 4: Revaleur anecdote — buyer messaged asking if an item was "still available" shortly after buying it

(Day 7+ material still untouched: jobs.py history, background.js/shared.js/marktplaats.js/tweedehands.js/vinted.js extension internals, schema.sql, content keyword queue, launch.json, the inject_comparison_screenshots feature — sandwiching real CrossList EU dashboard screenshots around the AI-generated comparison table in pillar-C competitor articles, plus expanding pillar-C prompt rules to require 7+ h2 sections / 2200-2800 words to make room for them, and the CROSSLIST_SCREENSHOTS list growing from a 2-entry dict to an ordered list of ~6+ real captures (dashboard, items, new-item form, refresh-vinted, etc).)

## 2026-07-10 (Day 7)
- Post 1: funny one-liner — fuzzy match (0.9 threshold) silently merged "navy bomber jacket men's L" and "...men's XL" into one listing
- Post 2: long devlog — the full "scan your existing listings" arc: schema.sql snapshot columns (photo_urls/description/brand/size/etc), fuzzy-match bug found and fixed with exact-title-only matching (imports.py `_best_match`/`_norm_title`), then realized exact title alone isn't safe either (duplicate titles across items) so added platform listing id as the real match signal (`same_listing` > `same_title` > new) plus retry-with-backoff on Vinted's flaky description fetch (background.js) and an og:description page-HTML fallback
- Post 3: medium process post — live scan progress panel + progress endpoint (21727a1), because the extension sat silent for 15-20s during a scan and felt broken even when it wasn't
- Post 4: Revaleur anecdote — packing orders, briefly forgetting which platform an item was even listed on pre-CrossList

(Day 8+ material still untouched: shared.js/marktplaats.js/tweedehands.js/vinted.js extension internals beyond background.js, content keyword queue, launch.json, the inject_comparison_screenshots feature — sandwiching real CrossList EU dashboard screenshots around the AI-generated comparison table in pillar-C competitor articles, plus expanding pillar-C prompt rules to require 7+ h2 sections / 2200-2800 words, and the CROSSLIST_SCREENSHOTS list growing from a 2-entry dict to an ordered list of ~6+ real captures. Also: the review UI's per-row Same listing/Same title/New diagnostic badges (a97b785/a9a1a49 frontend side, app.html) haven't been mined for a post yet.)

## 2026-07-11 (Day 8)
- Post 1: funny one-liner — waking up to a trademark claim email on the name "crosslist"
- Post 2: long devlog — the full same-day forced rebrand: trademark claim → strip "CrossList EU" from 234 occurrences (UI, blog templates, emails, extension) to temp placeholder "ListHub" first (to stay live/unexposed), then the DB-level work (17 published blog articles, domain detach/repoint) that took longer than the code itself; lesson that a brand name is spread across way more surfaces than it looks
- Post 3: medium decision post — landed on final name Omnivaleur ("omni" = list everywhere, "valeur" = shared root with Revaleur), the tool inheriting the shop's "last name"
- Post 4: Revaleur reflection — noticing "Revaleur" was the one brand mention left untouched in the rebrand sweep, contrasting how fast a SaaS name can change vs. 700+ reviews of built-up reputation

(Day 9+ material still untouched: shared.js/marktplaats.js/tweedehands.js/vinted.js extension internals beyond background.js, launch.json, the inject_comparison_screenshots feature, review UI diagnostic badges (a97b785/a9a1a49). New from today: Chrome Web Store re-listing under Omnivaleur still pending on Daniel's end, Railway analytics token swap still pending, EUIPO trademark verification for "Omnivaleur" still pending — could make good "still chasing this down" follow-up posts in a few days once resolved.)

## 2026-07-17 (Day 9)
- Post 1: funny one-liner — Vinted relist bug: submitListing timed out and reported "failed" because Vinted's moderation review delays the /items/{id} redirect, even though the item was already live
- Post 2: long devlog — fixing notification scrapers against live Marktplaats/Vinted: Vinted was a wrong deep link (/member/messages 404s, needed /inbox) plus switching to the /api/v2/inbox endpoint for real unread/offer counts; Marktplaats/2dehands offer-detection was overcounting because it flagged any message mentioning a price, fixed by matching literal "bod" instead
- Post 3: medium process/decision post — eBay listing flow upgrade (#1): replaced the free-text numeric category ID field with a debounced dropdown that suggests categories from the title as you type, preselects the top match, keeps manual ID entry as a fallback, and preserves a saved category on edit
- Post 4: Revaleur anecdote — sourcing trip turned up a Barbour jacket in rare condition, paid more than planned, photographed it same day anyway

## 2026-09-04 (Day 10)
- Post 1: funny one-liner — asked the translator to translate English into English; model replied "I notice you haven't included any text to translate" and that sentence got published verbatim as a listing title (81a4a74, translation guard)
- Post 2: long devlog — the landing-page honesty rewrite (d2d06a5/335b583): homepage promised "AI listings from a photo" (endpoint existed, no button ever wired to it) and had invented stats ("3x more reach", "90% less work"), while hiding the features the app actually gained (bulk import, unified inbox, profit analytics, stale-stock price ladder); rebuilt the page 1:1 with the real app, added an "Inside the app" tour that rebuilds the actual sidebar, cut the fake numbers, added Facebook Marketplace as a beta with the honest account-ban warning
- Post 3: medium devlog — Vinted description line breaks getting collapsed into one blob because Lexical flattens a multi-line insertText, fixed by inserting line-by-line with insertParagraph; same session, the Vinted category picker was unusable for non-clothing (games/electronics) because the search input blurred on type and closed the dropdown (62d423e)
- Post 4: Revaleur anecdote — six dead days of listing/relisting/price drops with total silence, then three items sold in about an hour one evening, two to the same buyer; sales clump, they're never steady

(Day 11+ material still untouched: PWA install support + platform notification icons (7747009), GA4 analytics added to the Chrome extension + activated Measurement Protocol secret (2742b2c/4077b95), switch to new Omnivaleur GA4 property (5886d38), extension build script (ce3bd5f), real platform interface screenshots added for blog content (f13295d), FAQ answers now rendered as HTML so links don't show as raw tags (1c5b234), Railway env-var check script (f961e6a), translation-guard fix so Claude translates instead of commenting on the text (81a4a74), plus backfill_repair_anchors.py/generator.py/linking.py/webapp_sync.js work from July 12-14 not yet mined. Note: repo directory was renamed from crosslist-eu to omnivaleur during the rebrand — future runs should check ~/Documents/omnivaleur if ~/Documents/crosslist-eu isn't a git repo.)
