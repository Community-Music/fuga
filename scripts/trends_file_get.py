import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

from fuga.api import FUGAV3Client, MemoryTokenStore
from fuga.trends import FUGATrends

load_dotenv()

CLIENT_ID = os.getenv("FUGA_CLIENT_ID")
CLIENT_SECRET = os.getenv("FUGA_CLIENT_SECRET")

api = FUGAV3Client(
    api_url="https://next.fugamusic.com/api/v3",
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    token_store=MemoryTokenStore(),
)

# get 1 hour ago from now (UTC)
target_datetime = datetime.now() - timedelta(hours=1)
print(f"Target datetime (UTC)= {target_datetime.isoformat()}")

# epoch milliseconds (Long)
updated_since = int(target_datetime.timestamp() * 1000)
print(f"Updated since epoch (ms)= {updated_since}")

params = {
    "updated_since": updated_since,  # IMPORTANT: int milliseconds
}
res = FUGATrends(api).trends_files_get(params=params)
print(f"Res= {res}")
