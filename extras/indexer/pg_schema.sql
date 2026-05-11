-- Alfred Products — PostgreSQL Schema
-- 比 SQLite 多了：price_history 歷史表、JSONB 擴充欄位、全文搜尋 tsvector

-- 商品主表
CREATE TABLE IF NOT EXISTS products (
    id               BIGSERIAL PRIMARY KEY,
    site             TEXT NOT NULL,
    code             TEXT NOT NULL,
    name             TEXT NOT NULL,
    brand            TEXT,
    category         TEXT,
    price            INTEGER NOT NULL,
    list_price       INTEGER,
    discount_pct     INTEGER,
    image_url        TEXT,
    buy_url          TEXT NOT NULL,
    rating           REAL,
    review_count     INTEGER,
    is_accessory     BOOLEAN DEFAULT FALSE,
    is_active        BOOLEAN DEFAULT TRUE,
    indexed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    price_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    search_vector    TSVECTOR,
    UNIQUE(site, code)
);

-- 價格歷史表（這是 SQLite 沒有的核心資產）
CREATE TABLE IF NOT EXISTS price_history (
    id         BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    site       TEXT NOT NULL,
    code       TEXT NOT NULL,
    price      INTEGER NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_products_site    ON products(site);
CREATE INDEX IF NOT EXISTS idx_products_price   ON products(price) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_products_updated ON products(price_updated_at);
CREATE INDEX IF NOT EXISTS idx_products_search  ON products USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_history_product  ON price_history(product_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_site_code ON price_history(site, code, recorded_at DESC);

-- 全文搜尋自動更新 trigger
CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('simple',
        COALESCE(NEW.name, '') || ' ' ||
        COALESCE(NEW.brand, '') || ' ' ||
        COALESCE(NEW.category, '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_search_vector ON products;
CREATE TRIGGER trg_search_vector
    BEFORE INSERT OR UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();

-- upsert 時自動寫 price_history
CREATE OR REPLACE FUNCTION record_price_history()
RETURNS TRIGGER AS $$
BEGIN
    -- 只有價格真正變動才記錄
    IF (TG_OP = 'INSERT') OR (OLD.price IS DISTINCT FROM NEW.price) THEN
        INSERT INTO price_history(product_id, site, code, price, recorded_at)
        VALUES (NEW.id, NEW.site, NEW.code, NEW.price, NOW());
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_price_history ON products;
CREATE TRIGGER trg_price_history
    AFTER INSERT OR UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION record_price_history();
