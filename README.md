# FUGA Catalog API

A Python client for FUGA's Catalog API: products, assets, artists, labels, people, publishing houses, delivery instructions, trends and uploads.

## Requirements

- Python 3.10 or later
- `requests`

## Installation

In another project, pin a release tag:

```zsh
pip install "git+https://github.com/Community-Music/fuga.git@v1.4.0#egg=fuga"
```

To work on the package itself:

```zsh
git clone https://github.com/Community-Music/fuga.git
cd fuga
pip install -e ".[dev]"
```

## Usage

```python
from fuga.api import FUGAClient
from fuga.product import FUGAProduct

# Logs in on the first request. Pass auth_cookie instead to reuse a session.
client = FUGAClient(API_URL, username=USERNAME, password=PASSWORD)

product = FUGAProduct(client)
response = product.create({"name": "New Album", "release_date": "2024-12-31"})

if response["success"]:
    print("Created product", product.product_id)
else:
    print("FUGA returned", response["status_code"], response["error"])
```

Every call returns a dict with `success` and `status_code`, plus `data` on success or `error` on failure; `status_code` is `None` when the request never reached FUGA. Calls don't raise, except that a refused login raises `fuga.api.FUGAAuthError`.

## Example scripts

The scripts in `scripts/` read `FUGA_USERNAME` and `FUGA_PASSWORD` from a `.env` file. Fill in the ids at the top of a script, then run it from the repository root:

```zsh
python -m scripts.delivery_instructions_fetch
```

## Tests

```zsh
pytest
```

The tests mock every HTTP call, so they need no FUGA account and make no network requests.
