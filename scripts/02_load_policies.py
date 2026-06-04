import pandas as pd
from sqlalchemy import create_engine
import random
from datetime import datetime, timedelta
import uuid
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus


load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD"))
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")


engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

print("🚀 Connected to database")


customers = pd.read_sql("SELECT customer_id FROM customers", engine)

if customers.empty:
    raise Exception("❌ No customers found. Load customers first.")

print(f"📊 Found {len(customers)} customers")


policy_types = ["Life", "Health", "Auto", "Education"]

def generate_policy(customer_id):
    start_date = datetime.today() - timedelta(days=random.randint(0, 1000))
    end_date = start_date + timedelta(days=365 * 5)

    return {
        "policy_id": str(uuid.uuid4()),
        "customer_id": customer_id,
        "policy_type": random.choice(policy_types),
        "premium": round(random.uniform(5000, 50000), 2),
        "start_date": start_date.date(),
        "end_date": end_date.date(),
        "status": "Active"
    }


policies = [
    generate_policy(row["customer_id"])
    for _, row in customers.iterrows()
]

df = pd.DataFrame(policies)

print(f"📊 Policies to insert: {len(df)}")


df.to_sql(
    "policies",
    engine,
    if_exists="append",
    index=False,
    chunksize=500,
    method="multi"
)

print("✅ Policies inserted successfully")