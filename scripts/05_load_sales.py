import pandas as pd
from sqlalchemy import create_engine
import uuid
import random
from datetime import datetime
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{quote_plus(os.getenv('DB_PASSWORD'))}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

policies = pd.read_sql("SELECT policy_id, customer_id, premium FROM policies", engine)
agents = pd.read_sql("SELECT agent_id FROM agents", engine)

sales = []

for _, row in policies.iterrows():
    agent = agents.sample(1).iloc[0]

    commission_rate = random.uniform(0.05, 0.15)

    sales.append({
        "sale_id": str(uuid.uuid4()),
        "policy_id": row["policy_id"],
        "customer_id": row["customer_id"],
        "agent_id": agent["agent_id"],
        "sale_date": datetime.now().date(),
        "commission_rate": round(commission_rate, 2),
        "commission_amount": round(row["premium"] * commission_rate, 2),
        "premium_amount": row["premium"]
    })

df = pd.DataFrame(sales)

df.to_sql("sales", engine, if_exists="append", index=False, method="multi")
print("✅ Sales loaded")