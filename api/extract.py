import os
import json
from datetime import datetime, date
from http.server import BaseHTTPRequestHandler
import anthropic

# Import shared config
from api._shared import json_response


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length))

        image_b64 = body.get("image")
        if not image_b64:
            self._respond(400, {"error": "No image provided"})
            return

        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self._respond(500, {"error": "ANTHROPIC_API_KEY not set"})
            return

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
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
                raw = raw.rsplit("```", 1)[0]
            result = json.loads(raw)

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
            self._respond(200, result)

        except json.JSONDecodeError:
            self._respond(500, {"error": "Could not parse AI response", "raw": raw})
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
