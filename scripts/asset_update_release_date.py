import os
from dotenv import load_dotenv

from fuga.api import FUGAClient
from fuga.asset import FUGAAsset

load_dotenv()

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

# Fill these in before running
ASSET_ID = "1009137292596"
ASSET_RELEASE_DATE = "2026-06-02"  # YYYY-MM-DD

api = FUGAClient(
    api_url="https://next.fugamusic.com/api/v2",
    username=USERNAME,
    password=PASSWORD,
)

asset = FUGAAsset(api, ASSET_ID)
res = asset.update({"asset_release_date": ASSET_RELEASE_DATE})
print(f"Res= {res}")
