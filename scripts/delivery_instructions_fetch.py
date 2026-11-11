import os

from dotenv import load_dotenv

from fuga.api import FUGAV3Client, MemoryTokenStore
from fuga.delivery_instructions import FUGADeliveryInstructions

load_dotenv()

CLIENT_ID = os.getenv("FUGA_CLIENT_ID")
CLIENT_SECRET = os.getenv("FUGA_CLIENT_SECRET")

# Fill this in before running
PRODUCT_ID = "1001642988874"

api = FUGAV3Client(
    api_url="https://next.fugamusic.com/api/v3",
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    token_store=MemoryTokenStore(),
)

di = FUGADeliveryInstructions(api, PRODUCT_ID)
res = di.fetch()
print(f"Res= {res}")
