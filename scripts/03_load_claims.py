import pandas as pd
from sqlalchemy import create_engine
import random
import uuid
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

# -------------------------
# LOAD ENV
# -------------------------
load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD"))
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# -------------------------
# DB ENGINE
# -------------------------
engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

print("🚀 Connected to DB")

# -------------------------
# FETCH POLICIES
# -------------------------
policies = pd.read_sql("""
    SELECT policy_id, customer_id, start_date, end_date
    FROM policies
""", engine)

if policies.empty:
    raise Exception("❌ No policies found. Load policies first.")

print(f"📊 Found {len(policies)} policies")

# -------------------------
# CLAIM TYPES
# -------------------------
claim_types = ["Medical", "Accident", "Theft", "Fire", "Death"]

statuses = ["Pending", "Approved", "Rejected", "Paid"]

# -------------------------
# GENERATE CLAIMS
# -------------------------
claims = []

for _, row in policies.iterrows():

    # 40% chance a policy has a claim
    if random.random() < 0.4:

        incident_date = row["start_date"] + timedelta(
            days=random.randint(30, 1500)
        )

        claim_amount = round(random.uniform(5000, 200000), 2)

        status = random.choice(statuses)

        approved_amount = (
            round(claim_amount * random.uniform(0.3, 1.0), 2)
            if status in ["Approved", "Paid"]
            else 0
        )

        claims.append({
            "claim_id": str(uuid.uuid4()),
            "policy_id": row["policy_id"],
            "customer_id": row["customer_id"],
            "claim_type": random.choice(claim_types),
            "claim_amount": claim_amount,
            "claim_status": status,
            "incident_date": incident_date,
            "claim_date": incident_date + timedelta(days=random.randint(1, 30)),
            "approved_amount": approved_amount,
            "created_at": datetime.now()
        })

df = pd.DataFrame(claims)

print(f"📊 Generated {len(df)} claims")

# -------------------------
# LOAD INTO POSTGRES
# -------------------------
df.to_sql(
    "claims",
    engine,
    if_exists="append",
    index=False,
    chunksize=500,
    method="multi"
)

print("✅ Claims loaded successfully")