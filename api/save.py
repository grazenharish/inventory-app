import json
from http.server import BaseHTTPRequestHandler
from api._shared import get_supabase, COLUMNS


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(content_length))

        supabase = get_supabase()
        record = {}
        cols = COLUMNS + ["photo_b64"]
        for c in cols:
            val = data.get(c)
            if c in ("stock_in_hand", "total_stocks", "outward_yesterday", "mtd_sale", "week_sale"):
                if val is not None and val != "":
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        val = None
                else:
                    val = None
            elif c in ("shelf_life", "remaining_shelf_life"):
                if val is not None and val != "":
                    try:
                        val = int(val)
                    except (ValueError, TypeError):
                        val = None
                else:
                    val = None
            record[c] = val

        try:
            supabase.table("inventory").insert(record).execute()
            self._respond(200, {"status": "saved"})
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
