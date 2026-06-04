"""
fact_payments ETL Pipeline
==========================
Pattern: Extract → Validate → Transform → Deduplicate → Load → Verify
Goal: Track every premium payment made against a policy
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
import random
import logging
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from config.db import engine

# -----------------------------
# LOGGING
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)


# -----------------------------
# 0. CREATE TABLE
# -----------------------------
def create_table():
    log.info("🏗️  Ensuring fact_payments table exists...")

    sql = """
    CREATE TABLE IF NOT EXISTS fact_payments (
        payment_id        VARCHAR(36)    PRIMARY KEY,
        policy_id         VARCHAR(36)    NOT NULL,
        customer_id       VARCHAR(36)    NOT NULL,
        date_key          DATE           NOT NULL REFERENCES dim_date(date_key),
        county_id         INTEGER        REFERENCES dim_county(county_id),
        policy_type_id    INTEGER        REFERENCES dim_policy_type(policy_type_id),

        -- Measures
        payment_amount    NUMERIC(12,2)  NOT NULL,
        expected_amount   NUMERIC(12,2)  NOT NULL,
        variance          NUMERIC(12,2)  GENERATED ALWAYS AS
                              (payment_amount - expected_amount) STORED,
        is_full_payment   BOOLEAN        GENERATED ALWAYS AS
                              (payment_amount >= expected_amount) STORED,

        -- Degenerate dimensions
        payment_method    VARCHAR(30),   -- 'Mpesa', 'Bank Transfer', 'Cash', 'Card'
        payment_status    VARCHAR(20),   -- 'Completed', 'Pending', 'Failed', 'Reversed'
        payment_frequency VARCHAR(20),   -- 'Monthly', 'Quarterly', 'Annual'
        is_late           BOOLEAN        DEFAULT FALSE,
        days_late         INTEGER        DEFAULT 0,
        payment_date      DATE,
        due_date          DATE,

        -- Metadata
        created_at        TIMESTAMP      DEFAULT NOW()
    );
    """

    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()

    log.info("  ✅ fact_payments table ready!")


# -----------------------------
# 1. EXTRACT
# -----------------------------
def extract():
    log.info("📥 EXTRACT — pulling source tables...")

    policies     = pd.read_sql("SELECT * FROM policies", engine)
    customers    = pd.read_sql("SELECT customer_id, county FROM dim_customer", engine)
    counties     = pd.read_sql("SELECT county_id, county_name FROM dim_county", engine)
    policy_types = pd.read_sql("SELECT policy_type_id, policy_type FROM dim_policy_type", engine)

    log.info(f"  policies     : {len(policies):,} rows")
    log.info(f"  customers    : {len(customers):,} rows")
    log.info(f"  counties     : {len(counties):,} rows")
    log.info(f"  policy_types : {len(policy_types):,} rows")

    return policies, customers, counties, policy_types


# -----------------------------
# 2. VALIDATE
# -----------------------------
def validate(policies):
    log.info("🔍 VALIDATE — checking source data quality...")

    issues = []
    issues.append(("null policy_id",    policies["policy_id"].isna().sum()))
    issues.append(("null customer_id",  policies["customer_id"].isna().sum()))
    issues.append(("null premium",      policies["premium"].isna().sum()))
    issues.append(("negative premium", (policies["premium"] < 0).sum()))
    issues.append(("null start_date",   policies["start_date"].isna().sum()))

    has_issues = False
    for name, count in issues:
        if count > 0:
            log.warning(f"  ⚠️  {name}: {count}")
            has_issues = True

    if not has_issues:
        log.info("  ✅ All source validations passed")

    return issues


# -----------------------------
# 3. TRANSFORM
# Generate realistic payment records per policy
# Each policy gets payments based on its frequency
# -----------------------------
def transform(policies, customers, counties, policy_types):
    log.info("🔧 TRANSFORM — generating payment records...")

    # Join county from dim_customer
    df = policies.merge(customers, on="customer_id", how="left")

    # Join county_id
    df = df.merge(
        counties,
        left_on="county",
        right_on="county_name",
        how="left"
    )

    # Join policy_type_id
    df = df.merge(policy_types, on="policy_type", how="left")

    payment_methods    = ["Mpesa", "Bank Transfer", "Cash", "Card"]
    payment_statuses   = ["Completed", "Completed", "Completed", "Pending", "Failed", "Reversed"]
    payment_frequencies = ["Monthly", "Quarterly", "Annual"]

    payments = []

    for _, row in df.iterrows():
        start_date = pd.to_datetime(row["start_date"]).date()
        end_date   = pd.to_datetime(row["end_date"]).date()
        today      = datetime.today().date()
        cutoff     = min(end_date, today)

        # Assign payment frequency
        frequency  = random.choice(payment_frequencies)

        # Calculate interval and installment amount
        if frequency == "Monthly":
            interval_days  = 30
            installment    = round(float(row["premium"]) / 12, 2)
        elif frequency == "Quarterly":
            interval_days  = 90
            installment    = round(float(row["premium"]) / 4, 2)
        else:  # Annual
            interval_days  = 365
            installment    = round(float(row["premium"]), 2)

        # Generate payments from start_date to today
        due_date = start_date
        while due_date <= cutoff:
            payment_date   = due_date + timedelta(days=random.randint(-3, 15))
            is_late        = payment_date > due_date
            days_late      = max(0, (payment_date - due_date).days)
            status         = random.choice(payment_statuses)

            # Partial payments occasionally
            payment_amount = installment
            if status == "Completed" and random.random() < 0.05:
                payment_amount = round(installment * random.uniform(0.7, 0.99), 2)
            elif status in ["Failed", "Reversed"]:
                payment_amount = 0.00

            payments.append({
                "payment_id":        str(uuid.uuid4()),
                "policy_id":         str(row["policy_id"]),
                "customer_id":       str(row["customer_id"]),
                "date_key":          payment_date,
                "county_id":         row.get("county_id"),
                "policy_type_id":    row.get("policy_type_id"),
                "payment_amount":    payment_amount,
                "expected_amount":   installment,
                "payment_method":    random.choice(payment_methods),
                "payment_status":    status,
                "payment_frequency": frequency,
                "is_late":           is_late,
                "days_late":         days_late,
                "payment_date":      payment_date,
                "due_date":          due_date,
            })

            due_date = due_date + timedelta(days=interval_days)

    fact = pd.DataFrame(payments)

    # Ensure date_key exists in dim_date
    valid_dates = pd.read_sql("SELECT date_key FROM dim_date", engine)
    valid_dates["date_key"] = pd.to_datetime(valid_dates["date_key"]).dt.date
    fact["date_key"] = pd.to_datetime(fact["date_key"]).dt.date
    before = len(fact)
    fact = fact[fact["date_key"].isin(valid_dates["date_key"])]
    dropped = before - len(fact)
    if dropped > 0:
        log.warning(f"  ⚠️  Dropped {dropped} rows with dates outside dim_date range")

    log.info(f"  Transformed rows : {len(fact):,}")
    log.info(f"  Null check       : {fact.isnull().sum().to_dict()}")

    # Payment method breakdown
    log.info(f"\n{fact['payment_method'].value_counts().to_string()}")
    log.info(f"\n{fact['payment_status'].value_counts().to_string()}")
    log.info(f"\n{fact['payment_frequency'].value_counts().to_string()}")

    return fact


# -----------------------------
# 4. DEDUPLICATE
# -----------------------------
def deduplicate(df):
    log.info("🔍 DEDUPLICATE — checking for existing records...")

    try:
        existing = pd.read_sql("SELECT payment_id FROM fact_payments", engine)
        before   = len(df)
        df       = df[~df["payment_id"].isin(existing["payment_id"])]
        log.info(f"  Skipped {before - len(df):,} duplicates. New rows: {len(df):,}")
    except Exception as e:
        log.warning(f"  Could not check existing records: {e}")

    return df


# -----------------------------
# 5. LOAD
# -----------------------------
def load(df):
    if df.empty:
        log.info("ℹ️  No new rows to load — skipping")
        return

    log.info(f"📤 LOAD — inserting {len(df):,} rows into fact_payments...")

    df.to_sql(
        "fact_payments",
        engine,
        if_exists="append",
        index=False,
        chunksize=100,   # ✅ safe
        method=None      # ✅ no overflow
    )

    log.info("  ✅ Load complete")


# -----------------------------
# 6. VERIFY
# -----------------------------
def verify():
    log.info("📊 VERIFY — post-load checks...")

    with engine.connect() as conn:
        total        = conn.execute(text("SELECT COUNT(*) FROM fact_payments")).scalar()
        null_amounts = conn.execute(text(
            "SELECT COUNT(*) FROM fact_payments WHERE payment_amount IS NULL"
        )).scalar()
        late_payments = conn.execute(text(
            "SELECT COUNT(*) FROM fact_payments WHERE is_late = TRUE"
        )).scalar()
        failed = conn.execute(text(
            "SELECT COUNT(*) FROM fact_payments WHERE payment_status IN ('Failed','Reversed')"
        )).scalar()
        total_collected = conn.execute(text(
            "SELECT ROUND(SUM(payment_amount),2) FROM fact_payments WHERE payment_status = 'Completed'"
        )).scalar()

    # Summary by method
    by_method = pd.read_sql("""
        SELECT
            payment_method,
            payment_status,
            COUNT(*)                        AS payments,
            ROUND(SUM(payment_amount), 2)   AS total_amount
        FROM fact_payments
        GROUP BY payment_method, payment_status
        ORDER BY payments DESC
        LIMIT 10
    """, engine)

    # Late payment analysis
    late_analysis = pd.read_sql("""
        SELECT
            pt.policy_type,
            COUNT(*) FILTER (WHERE fp.is_late = TRUE)  AS late_payments,
            COUNT(*) FILTER (WHERE fp.is_late = FALSE) AS on_time_payments,
            ROUND(AVG(fp.days_late), 1)                AS avg_days_late
        FROM fact_payments fp
        JOIN dim_policy_type pt ON fp.policy_type_id = pt.policy_type_id
        GROUP BY pt.policy_type
        ORDER BY late_payments DESC
    """, engine)

    log.info(f"  Total payments     : {total:,}")
    log.info(f"  Null amounts       : {null_amounts}")
    log.info(f"  Late payments      : {late_payments:,}")
    log.info(f"  Failed/Reversed    : {failed:,}")
    log.info(f"  Total collected    : KES {total_collected:,}")
    log.info(f"\nBy Method & Status:\n{by_method.to_string(index=False)}")
    log.info(f"\nLate Payment Analysis:\n{late_analysis.to_string(index=False)}")

    if null_amounts == 0:
        log.info("  ✅ All post-load checks passed")
    else:
        log.warning("  ⚠️  Issues found — investigate above")


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    start = datetime.now()

    log.info("=" * 55)
    log.info("🚀 FACT_PAYMENTS ETL PIPELINE STARTED")
    log.info("=" * 55)

    try:
        create_table()
        policies, customers, counties, policy_types = extract()
        validate(policies)
        fact = transform(policies, customers, counties, policy_types)
        fact = deduplicate(fact)
        load(fact)
        verify()

        duration = (datetime.now() - start).seconds
        log.info("=" * 55)
        log.info(f"🎉 PIPELINE COMPLETE in {duration}s")
        log.info("=" * 55)

    except Exception as e:
        log.error(f"❌ PIPELINE FAILED: {e}")
        raise