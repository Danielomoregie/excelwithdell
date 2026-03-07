import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("DATABASE_URL not found. Check your .env file.")
    raise SystemExit(1)

VERSION = "003_create_fusiontech_product_and_reviews"


def ensure_schema_migrations(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )


def migration_applied(cur):
    cur.execute(
        "SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = %s);",
        (VERSION,),
    )
    return cur.fetchone()[0]


def main():
    conn = None
    try:
        print("Connecting to Neon database...")
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        ensure_schema_migrations(cur)
        conn.commit()

        if migration_applied(cur):
            print(f"Migration {VERSION} already applied. Skipping.")
            cur.close()
            conn.close()
            return

        print("Creating table: FusionTech_Product")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS "FusionTech_Product" (
                product_id SERIAL PRIMARY KEY,
                title_y TEXT UNIQUE NOT NULL,
                asin TEXT,
                main_category TEXT,
                average_rating TEXT,
                rating_number TEXT,
                features TEXT,
                price TEXT,
                store TEXT,
                brand TEXT,
                default_os TEXT,
                default_color TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )

        print("Creating table: fusiontech_submitted_reviews")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS fusiontech_submitted_reviews (
                review_id BIGSERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES "FusionTech_Product"(product_id),
                rating INTEGER NOT NULL,
                title_x TEXT NOT NULL,
                text TEXT NOT NULL,
                asin TEXT,
                user_id TEXT,
                timestamp BIGINT NOT NULL,
                helpful_vote INTEGER NULL,
                main_category TEXT,
                title_y TEXT,
                average_rating TEXT,
                rating_number TEXT,
                features TEXT,
                price TEXT,
                store TEXT,
                os TEXT,
                color TEXT,
                brand TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_submitted_reviews_product_id
            ON fusiontech_submitted_reviews(product_id);
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_submitted_reviews_timestamp
            ON fusiontech_submitted_reviews(timestamp DESC);
            """
        )

        print("Seeding FusionTech_Product from online_reviews (if table exists)...")
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'online_reviews'
            );
            """
        )
        has_online_reviews = cur.fetchone()[0]

        if has_online_reviews:
            cur.execute(
                """
                INSERT INTO "FusionTech_Product"
                    (title_y, asin, main_category, average_rating, rating_number, features, price, store, brand, default_os, default_color)
                SELECT DISTINCT ON (title_y)
                    title_y,
                    asin,
                    main_category,
                    average_rating,
                    rating_number,
                    features,
                    price,
                    store,
                    brand,
                    os,
                    color
                FROM online_reviews
                WHERE title_y IS NOT NULL AND TRIM(title_y) <> ''
                ORDER BY title_y, COALESCE(rating_number::TEXT, '') DESC, COALESCE(asin, '') ASC
                ON CONFLICT (title_y) DO UPDATE SET
                    asin = EXCLUDED.asin,
                    main_category = EXCLUDED.main_category,
                    average_rating = EXCLUDED.average_rating,
                    rating_number = EXCLUDED.rating_number,
                    features = EXCLUDED.features,
                    price = EXCLUDED.price,
                    store = EXCLUDED.store,
                    brand = EXCLUDED.brand,
                    default_os = EXCLUDED.default_os,
                    default_color = EXCLUDED.default_color;
                """
            )
        else:
            print("online_reviews table not found, skipped product seeding.")

        cur.execute(
            """
            INSERT INTO schema_migrations (version) VALUES (%s)
            ON CONFLICT (version) DO NOTHING;
            """,
            (VERSION,),
        )

        conn.commit()
        print(f"Migration {VERSION} applied successfully.")

        cur.close()
        conn.close()

    except Exception as exc:
        print("Operation failed:")
        print(exc)
        if conn:
            conn.rollback()
            conn.close()
        raise


if __name__ == "__main__":
    main()
