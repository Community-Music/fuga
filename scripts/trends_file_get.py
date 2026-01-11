from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

from fuga.api import FUGAClient
from fuga.trends import trends_files_get

load_dotenv()

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

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
res = trends_files_get(api, params=params)
print(f"Res= {res}")
