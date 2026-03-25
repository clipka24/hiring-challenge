import sqlite3
import csv

# ─────────────────────────────────────────────
# 1. Datenbank & Tabelle aufsetzen
# ─────────────────────────────────────────────
conn = sqlite3.connect(":memory:")
cur = conn.cursor()

cur.execute("""
    CREATE TABLE user_events (
        user_id     INTEGER,
        teaser_id   INTEGER,
        event_type  TEXT,
        timestamp   TEXT,
        device_type TEXT,
        country     TEXT
    )
""")

# ─────────────────────────────────────────────
# 2. CSV einlesen (Semikolon-getrennt)
# ─────────────────────────────────────────────
CSV_PATH = "user_events.csv"  # Pfad zur CSV anpassen falls nötig

with open(CSV_PATH, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter=";")
    rows = [
        (row["user_id"], row["teaser_id"], row["event_type"],
         row["timestamp"], row["device_type"], row["country"])
        for row in reader
    ]

cur.executemany("""
    INSERT INTO user_events VALUES (?, ?, ?, ?, ?, ?)
""", rows)
conn.commit()
print(f"✅ {len(rows)} Zeilen importiert\n")

# das sollten
# cat user_events.csv | wc -l
#     5001
# Zeilen sein, also 5k events + header


# ─────────────────────────────────────────────
# Teil A – CTR pro teaser_id (Jahr 2022)
# ─────────────────────────────────────────────
print("=" * 55)
print("TEIL A – CTR pro teaser_id (2022)")
print("=" * 55)

query_a = """
SELECT
    teaser_id,
    SUM(CASE WHEN event_type = 'click'       THEN 1 ELSE 0 END) AS clicks,
    SUM(CASE WHEN event_type = 'impression'  THEN 1 ELSE 0 END) AS impressions,
    ROUND(
        CAST(SUM(CASE WHEN event_type = 'click'      THEN 1 ELSE 0 END) AS REAL)
        / NULLIF(SUM(CASE WHEN event_type = 'impression' THEN 1 ELSE 0 END), 0),
    2) AS ctr
FROM user_events
WHERE strftime('%Y', timestamp) = '2022'
GROUP BY teaser_id
ORDER BY teaser_id
"""

cur.execute(query_a)
rows_a = cur.fetchall()

print(f"{'teaser_id':<12} {'clicks':<10} {'impressions':<14} {'ctr':<8}")
print("-" * 46)
for row in rows_a:
    print(f"{row[0]:<12} {row[1]:<10} {row[2]:<14} {row[3]:<8}")


# =======================================================
# TEIL A – CTR pro teaser_id (2022)
# =======================================================
# teaser_id    clicks     impressions    ctr
# ----------------------------------------------
# 123          70         441            0.16
# 456          68         442            0.15
# 789          84         498            0.17

# ─────────────────────────────────────────────
# Teil B – Top-2-Länder CTR-Vergleich pro teaser_id
# ─────────────────────────────────────────────
print("\n" + "=" * 75)
print("TEIL B – Top-2-Länder CTR-Vergleich pro teaser_id (2022)")
print("=" * 75)

query_b = """
WITH country_stats AS (
    -- CTR pro teaser_id + country
    SELECT
        teaser_id,
        country,
        SUM(CASE WHEN event_type = 'click'      THEN 1 ELSE 0 END) AS clicks,
        SUM(CASE WHEN event_type = 'impression' THEN 1 ELSE 0 END) AS impressions,
        ROUND(
            CAST(SUM(CASE WHEN event_type = 'click'      THEN 1 ELSE 0 END) AS REAL)
            / NULLIF(SUM(CASE WHEN event_type = 'impression' THEN 1 ELSE 0 END), 0),
        2) AS ctr
    FROM user_events
    WHERE strftime('%Y', timestamp) = '2022'
    GROUP BY teaser_id, country
),
ranked AS (
    -- Länder nach Clicks ranken
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY teaser_id ORDER BY clicks DESC) AS rnk
    FROM country_stats
),
teaser_with_min2 AS (
    -- Nur teaser_id mit mindestens 2 Ländern
    SELECT teaser_id
    FROM ranked
    GROUP BY teaser_id
    HAVING COUNT(*) >= 2
),
top2 AS (
    -- auf die Top 2 Länder filtern   
    SELECT r.*
    FROM ranked r
    JOIN teaser_with_min2 t ON r.teaser_id = t.teaser_id
    WHERE r.rnk <= 2
),
pivot AS (
    SELECT
        teaser_id,
        MAX(CASE WHEN rnk = 1 THEN country END) AS top_country_1,
        MAX(CASE WHEN rnk = 1 THEN ctr     END) AS ctr_country_1,
        MAX(CASE WHEN rnk = 2 THEN country END) AS top_country_2,
        MAX(CASE WHEN rnk = 2 THEN ctr     END) AS ctr_country_2
    FROM top2
    GROUP BY teaser_id
)
SELECT
    teaser_id,
    top_country_1,
    ctr_country_1,
    top_country_2,
    ctr_country_2,
    -- Prozentuale Differenz: (CTR1 - CTR2) / CTR2 * 100
    ROUND(
        (ctr_country_1 - ctr_country_2)
        / NULLIF(ctr_country_2, 0) * 100,
    2) AS ctr_diff
FROM pivot
ORDER BY teaser_id
"""

cur.execute(query_b)
rows_b = cur.fetchall()

print(f"{'teaser_id':<12} {'top_country_1':<16} {'ctr_country_1':<16} "
      f"{'top_country_2':<16} {'ctr_country_2':<16} {'ctr_diff %':<10}")
print("-" * 88)
for row in rows_b:
    print(f"{row[0]:<12} {row[1]:<16} {row[2]:<16} {row[3]:<16} {row[4]:<16} {row[5]:<10}")

conn.close()

# ===========================================================================
# TEIL B – Top-2-Länder CTR-Vergleich pro teaser_id (2022)
# ===========================================================================
# teaser_id    top_country_1    ctr_country_1    top_country_2    ctr_country_2    ctr_diff %
# ----------------------------------------------------------------------------------------
# 123          FR               0.2              DE               0.17             17.65
# 456          DE               0.15             US               0.17             -11.76
# 789          FR               0.19             US               0.15             26.67