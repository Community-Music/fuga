import os

from dotenv import load_dotenv

from fuga.api import FUGAV3Client, MemoryTokenStore
from fuga.asset import FUGAAsset

load_dotenv()

CLIENT_ID = os.getenv("FUGA_CLIENT_ID")
CLIENT_SECRET = os.getenv("FUGA_CLIENT_SECRET")

# Fill these in before running
PRODUCT_ID = "1009137290231"
ASSET_ID = "1009137292596"

api = FUGAV3Client(
    api_url="https://next.fugamusic.com/api/v3",
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    token_store=MemoryTokenStore(),
)

# Per FUGA: the four preorder fields must always be sent together.
payload = {
    "name": "Test Track Name",
    "available_separately": True,
    "allow_preorder": True,
    "allow_preorder_preview": False,
    "preorder_type": "INSTANT_GRATIFICATION",  # "STANDARD" or "INSTANT_GRATIFICATION" or "PREORDER_ONLY"
    "asset_release_date": "2026-06-03",  # YYYY-MM-DD
}

asset = FUGAAsset(api, ASSET_ID)
res = asset.attach_to_product(PRODUCT_ID, payload)
print(f"Res= {res}")
