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

counties = ["Nairobi", "Kiambu", "Mombasa", "Nakuru", "Kisumu"]

agents = []

for _ in range(50):
    agents.append({
        "agent_id": str(uuid.uuid4()),
        "full_name": f"Agent {uuid.uuid4().hex[:6]}",
        "phone": f"07{random.randint(10000000,99999999)}",
        "email": f"agent{random.randint(1,9999)}@insurance.co.ke",
        "county": random.choice(counties),
        "hire_date": datetime.now().date(),
        "status": "Active"
    })

df = pd.DataFrame(agents)

df.to_sql("agents", engine, if_exists="append", index=False, method="multi")
print("✅ Agents loaded")