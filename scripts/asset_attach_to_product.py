import os
from dotenv import load_dotenv

from fuga.api import FUGAClient
from fuga.asset import FUGAAsset

load_dotenv()

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

# Fill these in before running
PRODUCT_ID = "1009137290231"
ASSET_ID = "1009137292596"

api = FUGAClient(
    api_url="https://next.fugamusic.com/api/v2",
    username=USERNAME,
    password=PASSWORD,
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
