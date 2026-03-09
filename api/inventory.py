import json
import re
from http.server import BaseHTTPRequestHandler
from api._shared import get_supabase, COLUMNS


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        supabase = get_supabase()
        try:
            result = supabase.table("inventory").select(
                "id, " + ", ".join(COLUMNS) + ", created_at"
            ).order("id", desc=True).execute()
            self._respond(200, result.data)
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def do_DELETE(self):
        # Extract item ID from path: /api/inventory/123
        match = re.search(r'/(\d+)$', self.path)
        if not match:
            self._respond(400, {"error": "No item ID"})
            return

        item_id = int(match.group(1))
        supabase = get_supabase()
        try:
            supabase.table("inventory").delete().eq("id", item_id).execute()
            self._respond(200, {"status": "deleted"})
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
