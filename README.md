# FUGA Catalog API

A Python client for FUGA's Catalog API: products, assets, artists, labels, people, publishing houses, delivery instructions, trends and uploads.

## Requirements

- Python 3.10 or later
- `requests`

## Installation

In another project, pin a release tag:

```zsh
pip install "git+https://github.com/Community-Music/fuga.git@v1.6.1#egg=fuga"
```

To work on the package itself:

```zsh
git clone https://github.com/Community-Music/fuga.git
cd fuga
pip install -e ".[dev]"
```

## Usage

The client talks to FUGA API v3 (`https://next.fugamusic.com/api/v3`). It gets a token with an API credential's client id and secret on the first request, keeps it in the token store it is given, and renews it before it expires.

```python
from fuga.api import FUGAV3Client, MemoryTokenStore
from fuga.product import FUGAProduct

# MemoryTokenStore suits one process. Processes that share a credential pass
# a shared store, such as a database row, so they share one token.
client = FUGAV3Client(
    API_URL,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    token_store=MemoryTokenStore(),
)

product = FUGAProduct(client)
response = product.create({"name": "New Album", "release_date": "2024-12-31"})

if response["success"]:
    print("Created product", product.product_id)
else:
    print("FUGA returned", response["status_code"], response["error"])
```

Every call returns a dict with `success` and `status_code`, plus `data` on success or `error` on failure; `status_code` is `None` when the request never reached FUGA. Calls don't raise, with one exception: when a client has no usable token and FUGA refuses to give it one, that raises `fuga.api.FUGAAuthError`. When FUGA rejects a token partway through, the client renews it once and retries; if that renewal fails too, the call returns FUGA's 401.

A process with no credential of its own, such as the video uploader, uses `FUGAV3TokenClient` with a token and expiry another process got. It never asks FUGA for a new token.

## Example scripts

The scripts in `scripts/` read `FUGA_CLIENT_ID` and `FUGA_CLIENT_SECRET` from a `.env` file. Fill in the ids at the top of a script, then run it from the repository root:

```zsh
python -m scripts.delivery_instructions_fetch
```

## Tests

```zsh
pytest
```

The tests mock every HTTP call, so they need no FUGA account and make no network requests.
