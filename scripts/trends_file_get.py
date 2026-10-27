import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

from fuga.api import FUGAClient
from fuga.trends import FUGATrends

load_dotenv()

USERNAME = os.getenv("FUGA_USERNAME")
PASSWORD = os.getenv("FUGA_PASSWORD")

api = FUGAClient(
    api_url="https://next.fugamusic.com/api/v2",
    username=USERNAME,
    password=PASSWORD,
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
