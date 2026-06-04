import pandas as pd
from sqlalchemy import create_engine
import uuid
import random
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{quote_plus(os.getenv('DB_PASSWORD'))}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

policies = pd.read_sql("SELECT policy_id, customer_id, premium FROM policies", engine)

payments = []

methods = ["M-Pesa", "Bank", "Card"]

for _, row in policies.iterrows():

    # simulate monthly payments
    for i in range(random.randint(1, 6)):

        payments.append({
            "payment_id": str(uuid.uuid4()),
            "policy_id": row["policy_id"],
            "customer_id": row["customer_id"],
            "payment_date": datetime.now().date() - timedelta(days=random.randint(0, 180)),
            "amount": round(row["premium"] / 6, 2),
            "payment_method": random.choice(methods),
            "status": "Completed"
        })

df = pd.DataFrame(payments)

df.to_sql("payments", engine, if_exists="append", index=False, method="multi")
print("✅ Payments loaded")