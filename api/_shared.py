import os
import json
from pathlib import Path
from supabase import create_client

# Load .env file (for local dev)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), val)

COLUMNS = [
    "location", "state", "type", "location_code", "brand", "pack", "sku",
    "item_code", "vareiant_code", "description", "batch_number",
    "stock_in_hand", "total_stocks", "dom", "shelf_life", "bbd",
    "today_date", "remaining_shelf_life", "shelf_life_pct",
    "outward_yesterday", "mtd_sale", "week_sale", "bbnd",
    "msku_description", "category"
]


def get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
    return create_client(url, key)


def json_response(data, status=200):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(data)
    }
