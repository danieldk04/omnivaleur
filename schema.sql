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
