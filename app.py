import os
import sqlite3
import json
import base64
from datetime import datetime, date
from pathlib import Path
from flask import Flask, render_template, request, jsonify, g
import anthropic

# Load .env file
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), val)

app = Flask(__name__)
DATABASE = os.path.join(os.path.dirname(__file__), "inventory.db")

COLUMNS = [
    "location", "state", "type", "location_code", "brand", "pack", "sku",
    "item_code", "vareiant_code", "description", "batch_number",
    "stock_in_hand", "total_stocks", "dom", "shelf_life", "bbd",
    "today_date", "remaining_shelf_life", "shelf_life_pct",
    "outward_yesterday", "mtd_sale", "week_sale", "bbnd",
    "msku_description", "category"
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT,
            state TEXT,
            type TEXT,
            location_code TEXT,
            brand TEXT,
            pack TEXT,
            sku TEXT,
            item_code TEXT,
            vareiant_code TEXT,
            description TEXT,
            batch_number TEXT,
            stock_in_hand REAL,
            total_stocks REAL,
            dom TEXT,
            shelf_life INTEGER,
            bbd TEXT,
            today_date TEXT,
            remaining_shelf_life INTEGER,
            shelf_life_pct TEXT,
            outward_yesterday REAL,
            mtd_sale REAL,
            week_sale REAL,
            bbnd TEXT,
            msku_description TEXT,
            category TEXT,
            photo_b64 TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    db.close()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/extract", methods=["POST"])
def extract():
    """Send image to Claude Vision API to extract label info."""
    data = request.get_json()
    image_b64 = data.get("image")
    if not image_b64:
        return jsonify({"error": "No image provided"}), 400

    # Remove data URL prefix if present
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set. Add it to .env"}), 500

    prompt = f"""You are an expert at reading product and warehouse labels. Carefully examine this image and extract every piece of text visible.

Read ALL text on the label including: product name, brand, flavor/variant, parent company, pack size, weight, barcode numbers, batch/lot numbers, manufacture date, expiry date, MRP, storage instructions, and whether it's retail or wholesale.

Then return a JSON object with these keys (use null for fields not visible on the label):

{{
    "brand": "brand name (e.g. Boomer, Orbit) - the product brand, not parent company",
    "description": "full product description: product name, flavor, type, and any key details like 'Wholesale Pack' or 'Non Retail Container'. Be thorough.",
    "pack": "pack size/weight (e.g. 200ml, 1kg, 2.112kg)",
    "sku": "SKU name or product variant",
    "item_code": "barcode number - read ALL digits below any barcode",
    "vareiant_code": "variant code if present",
    "batch_number": "batch/lot number",
    "dom": "date of manufacture (DD-MM-YYYY)",
    "shelf_life": "shelf life in days (if stated in months, convert to days)",
    "bbd": "best before/expiry date (DD-MM-YYYY). If label says 'Best before X months from MFG date', calculate it.",
    "today_date": "{date.today().strftime('%d-%m-%Y')}",
    "msku_description": "MRP/price info, parent company (e.g. Wrigley), storage instructions, and any other notable label text",
    "category": "product category (e.g. Confectionery, Beverages, Snacks, Dairy)",
    "location": "warehouse/city if on label, else null",
    "state": "state if on label, else null",
    "type": "warehouse type like CFA if on label, else null",
    "location_code": "location code if on label, else null",
    "stock_in_hand": null,
    "total_stocks": null,
    "remaining_shelf_life": null,
    "shelf_life_pct": null,
    "outward_yesterday": null,
    "mtd_sale": null,
    "week_sale": null,
    "bbnd": null
}}

IMPORTANT:
- Read EVERY piece of text on the label, even small print
- Include flavor/variant in the description (e.g. "Watermelon Flavour")
- Note if it's a wholesale/non-retail pack in the description
- Put parent company, storage instructions, and other details in msku_description
- For dates, use DD-MM-YYYY format
- Return ONLY valid JSON, no explanation."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]
        result = json.loads(raw)

        # Calculate remaining shelf life and percentage if possible
        try:
            if result.get("bbd"):
                bbd_date = datetime.strptime(result["bbd"], "%d-%m-%Y").date()
                today = date.today()
                remaining = (bbd_date - today).days
                result["remaining_shelf_life"] = remaining
                if result.get("shelf_life") and int(result["shelf_life"]) > 0:
                    pct = round((remaining / int(result["shelf_life"])) * 100)
                    result["shelf_life_pct"] = f"{pct}%"
        except (ValueError, TypeError):
            pass

        result["today_date"] = date.today().strftime("%d-%m-%Y")
        return jsonify(result)

    except json.JSONDecodeError:
        return jsonify({"error": "Could not parse AI response", "raw": raw}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/save", methods=["POST"])
def save():
    """Save an inventory record."""
    data = request.get_json()
    db = get_db()
    cols = COLUMNS + ["photo_b64"]
    values = [data.get(c) for c in cols]
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    db.execute(f"INSERT INTO inventory ({col_names}) VALUES ({placeholders})", values)
    db.commit()
    return jsonify({"status": "saved"})


@app.route("/api/inventory")
def list_inventory():
    """List all inventory records."""
    db = get_db()
    rows = db.execute(
        "SELECT id, " + ", ".join(COLUMNS) + ", created_at FROM inventory ORDER BY id DESC"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/inventory/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    db = get_db()
    db.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    db.commit()
    return jsonify({"status": "deleted"})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5050, debug=True, use_reloader=False)
