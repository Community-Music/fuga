import os
from dotenv import load_dotenv

from fuga.api import FUGAClient
from fuga.delivery_instructions import FUGADeliveryInstructions

load_dotenv()

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

# Fill this in before running
PRODUCT_ID = "1001642988874"

api = FUGAClient(
    api_url="https://next.fugamusic.com/api/v2",
    username=USERNAME,
    password=PASSWORD,
)

di = FUGADeliveryInstructions(api, PRODUCT_ID)
res = di.fetch()
print(f"Res= {res}")
