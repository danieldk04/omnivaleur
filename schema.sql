-- CrossList EU — Supabase/PostgreSQL schema
-- Run this in the Supabase SQL editor to initialise the database.

CREATE TABLE IF NOT EXISTS items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001',
    sku VARCHAR(50) UNIQUE,
    title VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(10,2),
    purchase_price DECIMAL(10,2),
    brand VARCHAR(100),
    size VARCHAR(20),
    condition VARCHAR(20) DEFAULT 'good',
    category VARCHAR(100),
    color VARCHAR(50),
    material VARCHAR(100),
    photo_urls TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    days_in_stock INT GENERATED ALWAYS AS
        (EXTRACT(DAY FROM NOW() - created_at)::INT) STORED
);

CREATE TABLE IF NOT EXISTS listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID REFERENCES items(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,
    platform_listing_id VARCHAR(100),
    platform_listing_url TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    listed_at TIMESTAMPTZ,
    sold_at TIMESTAMPTZ,
    last_checked TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS platform_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    platform VARCHAR(50) NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMPTZ,
    extra_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, platform)
);

CREATE TABLE IF NOT EXISTS sync_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id UUID REFERENCES listings(id),
    event_type VARCHAR(50),
    payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Job queue: Chrome extension polls this to pick up crosslist/delist tasks
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001',
    item_id UUID REFERENCES items(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,
    action VARCHAR(20) NOT NULL,          -- 'create' or 'delete'
    status VARCHAR(20) DEFAULT 'pending', -- pending / claimed / done / error
    payload JSONB,                        -- item data snapshot for extension
    result JSONB,                         -- {listing_id, listing_url} or {error}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    claimed_at TIMESTAMPTZ,
    done_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_jobs_status_platform ON jobs(status, platform);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_listings_item_id ON listings(item_id);
CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status);
CREATE INDEX IF NOT EXISTS idx_listings_platform ON listings(platform);
CREATE INDEX IF NOT EXISTS idx_sync_events_listing_id ON sync_events(listing_id);

-- Subscription tracking (synced via Stripe webhooks)
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    status VARCHAR(20) DEFAULT 'trialing', -- trialing / active / canceled / past_due
    plan VARCHAR(20) DEFAULT 'pro',
    trial_ends_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '7 days'),
    current_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- eBay support: items need a numeric eBay category ID to publish (eBay's
-- Inventory API requires a leaf category, unlike Marktplaats/Vinted's free-form
-- categories); listings need the offerId separately from the public listingId
-- since eBay's offer-level endpoints (withdraw/status) are keyed by offerId.
ALTER TABLE items ADD COLUMN IF NOT EXISTS ebay_category_id VARCHAR(50);
ALTER TABLE listings ADD COLUMN IF NOT EXISTS platform_offer_id VARCHAR(100);

-- Per-platform price overrides for eBay and Shopify (mirrors the existing
-- price_marktplaats/price_2dehands/price_vinted columns).
ALTER TABLE items ADD COLUMN IF NOT EXISTS price_ebay NUMERIC(10,2);
ALTER TABLE items ADD COLUMN IF NOT EXISTS price_shopify NUMERIC(10,2);

-- Listing refresh ("bump" old listings): tracked per-listing so we can enforce
-- a cooldown and expose "last refreshed" in the dashboard.
ALTER TABLE listings ADD COLUMN IF NOT EXISTS last_refreshed_at TIMESTAMPTZ;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS refresh_count INT DEFAULT 0;
-- Consecutive "not found" polls before we trust it enough to auto-delist — a single
-- 404 is often a stale/expired polling session, not a genuinely removed listing.
ALTER TABLE listings ADD COLUMN IF NOT EXISTS not_found_count INT DEFAULT 0;

-- Jobs can be scheduled for the future (used to jitter the "recreate" half of
-- a relist so delete→create doesn't fire back-to-back like a script).
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS scheduled_for TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_jobs_scheduled_for ON jobs(scheduled_for);

-- Per-user daily refresh counter, used to cap total refresh actions/day
-- regardless of how many items a user tries to refresh at once.
CREATE TABLE IF NOT EXISTS refresh_quota (
    user_id UUID NOT NULL,
    day DATE NOT NULL DEFAULT CURRENT_DATE,
    count INT DEFAULT 0,
    PRIMARY KEY (user_id, day)
);

-- Listing import: 'scan' jobs (extension reads the user's own "my listings"
-- page on a platform and reports back what it finds) land here for manual
-- review before being linked to an existing item or turned into a new one.
-- Nothing here is auto-applied — scraped data can only cover what's visible
-- on a listing card (title/price/photo/url), never fields like purchase
-- price, condition, color etc., so a human confirms before it becomes real data.
CREATE TABLE IF NOT EXISTS import_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    platform VARCHAR(50) NOT NULL,
    platform_listing_id VARCHAR(100) NOT NULL,
    platform_listing_url TEXT,
    title TEXT,
    price NUMERIC(10,2),
    photo_url TEXT,
    suggested_item_id UUID REFERENCES items(id) ON DELETE SET NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending / linked / imported / ignored
    created_at TIMESTAMPTZ DEFAULT NOW(),
    platform_listed_at TIMESTAMPTZ, -- when the scrape says it actually went live on the platform, if known
    UNIQUE(user_id, platform, platform_listing_id)
);
CREATE INDEX IF NOT EXISTS idx_import_candidates_user_platform ON import_candidates(user_id, platform, status);
ALTER TABLE import_candidates ADD COLUMN IF NOT EXISTS platform_listed_at TIMESTAMPTZ;

-- Programmatic SEO/GEO content pages (comparison posts, niche pages).
-- One row = one published URL. `intent_key` is the cannibalization guard:
-- region + pillar + slug together identify a single search intent, so a
-- re-run for the same intent updates this row instead of creating a new one.
CREATE TABLE IF NOT EXISTS content_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pillar VARCHAR(1) NOT NULL,          -- 'A' (platform combo) or 'B' (niche/audience)
    region VARCHAR(10) NOT NULL,         -- nl / be-nl / be-fr / fr / de
    slug VARCHAR(150) NOT NULL,          -- e.g. marktplaats-naar-vinted
    intent_key VARCHAR(200) GENERATED ALWAYS AS (region || ':' || pillar || ':' || slug) STORED UNIQUE,
    primary_keyword TEXT NOT NULL,
    title VARCHAR(70) NOT NULL,
    meta_description VARCHAR(160) NOT NULL,
    h1 TEXT NOT NULL,
    quick_answer TEXT NOT NULL,          -- 40-60 word answer block, rendered as <blockquote>
    takeaways TEXT[] DEFAULT '{}',       -- 3-5 one-line key facts, rendered as a highlighted callout box
    body_html TEXT NOT NULL,             -- H2 question-headings + body, SSR'd as-is
    faq JSONB NOT NULL DEFAULT '[]',     -- [{question, answer}, ...]
    featured_image_url TEXT,
    software_application_json_ld JSONB,
    article_json_ld JSONB,
    competitor_research JSONB,           -- top-3 SERP snapshot + heading map + content-gap notes, kept for audit/re-runs
    related_slugs TEXT[] DEFAULT '{}',   -- intent_keys of pages linked to/from (orphan-prevention)
    status VARCHAR(20) DEFAULT 'draft',  -- draft / published
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_content_pages_region_pillar ON content_pages(region, pillar, status);
CREATE INDEX IF NOT EXISTS idx_content_pages_status ON content_pages(status);

-- English is the default site language everywhere. Marktplaats/2dehands
-- articles additionally get an auto-translated Dutch companion page at the
-- same region+pillar with slug + '-nl' — `translation_of` points at the
-- English row's intent_key so both pages can render a language switcher.
ALTER TABLE content_pages ADD COLUMN IF NOT EXISTS language VARCHAR(5) DEFAULT 'en';
ALTER TABLE content_pages ADD COLUMN IF NOT EXISTS translation_of VARCHAR(200);
CREATE INDEX IF NOT EXISTS idx_content_pages_translation_of ON content_pages(translation_of);
