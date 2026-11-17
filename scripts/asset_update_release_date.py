import os

from dotenv import load_dotenv

from fuga.api import FUGAV3Client, MemoryTokenStore
from fuga.asset import FUGAAsset

load_dotenv()

CLIENT_ID = os.getenv("FUGA_CLIENT_ID")
CLIENT_SECRET = os.getenv("FUGA_CLIENT_SECRET")

# Fill these in before running
ASSET_ID = "1009137292596"
ASSET_RELEASE_DATE = "2026-06-02"  # YYYY-MM-DD

api = FUGAV3Client(
    api_url="https://next.fugamusic.com/api/v3",
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    token_store=MemoryTokenStore(),
)

asset = FUGAAsset(api, ASSET_ID)
res = asset.update({"asset_release_date": ASSET_RELEASE_DATE})
print(f"Res= {res}")
