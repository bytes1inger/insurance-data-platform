from faker import Faker
import pandas as pd
from sqlalchemy import create_engine
from urllib.parse import quote_plus
import uuid
from datetime import datetime
import os
from dotenv import load_dotenv

# -----------------------------
# 0. LOAD ENV (OPTION 2 FIX)
# -----------------------------
load_dotenv()

fake = Faker()

print("🚀 Generating customers...")

# -----------------------------
# 1. GENERATE DATA
# -----------------------------
data = []

for _ in range(1000):
    data.append({
        "customer_id": str(uuid.uuid4()),
        "full_name": fake.name(),
        "age": fake.random_int(18, 80),
        "gender": fake.random_element(["Male", "Female"]),
        "county": fake.random_element(["Nairobi", "Kiambu", "Mombasa", "Nakuru", "Kisumu"]),
        "signup_date": fake.date_between(start_date="-5y", end_date="today"),
        "ingested_at": datetime.now()
    })

df = pd.DataFrame(data)

print("📊 DataFrame shape:", df.shape)


db_user = os.getenv("DB_USER")
db_password = quote_plus(os.getenv("DB_PASSWORD"))
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")

engine = create_engine(
    f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
)


print("🚀 Checking existing customers...")

existing_ids = pd.read_sql("SELECT customer_id FROM customers", engine)

df = df[~df["customer_id"].isin(existing_ids["customer_id"])]

print(f"📉 New records after dedup: {len(df)}")


print("🚀 Loading into Postgres...")

df.to_sql(
    "customers",
    engine,
    if_exists="append",
    index=False,
    chunksize=500,
    method="multi"
)

print("✅ Customers loaded successfully")