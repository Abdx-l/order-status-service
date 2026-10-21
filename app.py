import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
from service import MemoryCache, OrderService, PostgresOrders, RedisCache, SQLiteOrders

PATH = re.compile(r"^/orders/([1-9][0-9]*)$")


def handler_for(service):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, code, value):
            body = json.dumps(value).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def order_id(self):
            match = PATH.fullmatch(self.path)
            return int(match.group(1)) if match else None

        def do_GET(self):
            order_id = self.order_id()
            if order_id is None: return self.send_json(404, {"error": "not found"})
            order = service.get(order_id)
            self.send_json(200 if order else 404, order or {"error": "not found"})

        def do_PUT(self):
            order_id = self.order_id()
            if order_id is None: return self.send_json(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 4096: raise ValueError("invalid body length")
                payload = json.loads(self.rfile.read(length))
                order = service.put(order_id, payload["status"])
                self.send_json(200, order)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                self.send_json(400, {"error": str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="orders.db")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--cache", choices=("memory", "redis"), default="memory")
    args = parser.parse_args()
    store = PostgresOrders(os.environ["DATABASE_URL"]) if os.environ.get("DATABASE_URL") else SQLiteOrders(args.db)
    cache = RedisCache(os.environ["REDIS_URL"]) if args.cache == "redis" else MemoryCache()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(OrderService(store, cache)))
    print(f"Listening on 127.0.0.1:{args.port}")
    server.serve_forever()


if __name__ == "__main__": main()

