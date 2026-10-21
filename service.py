import json
import sqlite3
import threading
import time


class MemoryCache:
    def __init__(self, clock=time.monotonic):
        self.data = {}
        self.clock = clock

    def get(self, key):
        value = self.data.get(key)
        if value is None or value[0] <= self.clock():
            self.data.pop(key, None)
            return None
        return value[1]

    def setex(self, key, ttl, value):
        self.data[key] = (self.clock() + ttl, value)

    def delete(self, key):
        self.data.pop(key, None)


class RedisCache:
    def __init__(self, url):
        import redis
        self.client = redis.from_url(url, decode_responses=True)

    def get(self, key): return self.client.get(key)
    def setex(self, key, ttl, value): self.client.setex(key, ttl, value)
    def delete(self, key): self.client.delete(key)


class SQLiteOrders:
    def __init__(self, path):
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, status TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1)")
        self.connection.commit()

    def get(self, order_id):
        row = self.connection.execute("SELECT id,status,version FROM orders WHERE id=?", (order_id,)).fetchone()
        return dict(zip(("id", "status", "version"), row)) if row else None

    def put(self, order_id, status):
        with self.connection:
            self.connection.execute("""INSERT INTO orders(id,status) VALUES(?,?)
                ON CONFLICT(id) DO UPDATE SET status=excluded.status,version=version+1""", (order_id, status))
        return self.get(order_id)


class PostgresOrders:
    def __init__(self, dsn):
        import psycopg
        self.connection = psycopg.connect(dsn)
        with self.connection:
            self.connection.execute("CREATE TABLE IF NOT EXISTS orders (id BIGINT PRIMARY KEY, status TEXT NOT NULL, version BIGINT NOT NULL DEFAULT 1)")

    def get(self, order_id):
        row = self.connection.execute("SELECT id,status,version FROM orders WHERE id=%s", (order_id,)).fetchone()
        return dict(zip(("id", "status", "version"), row)) if row else None

    def put(self, order_id, status):
        with self.connection:
            self.connection.execute("""INSERT INTO orders(id,status) VALUES(%s,%s)
                ON CONFLICT(id) DO UPDATE SET status=excluded.status,version=orders.version+1""", (order_id, status))
        return self.get(order_id)


class OrderService:
    def __init__(self, store, cache, ttl=30):
        self.store, self.cache, self.ttl = store, cache, ttl
        self.lock = threading.RLock()

    def get(self, order_id):
        with self.lock:
            key = f"order:{order_id}"
            cached = self.cache.get(key)
            if cached is not None:
                return json.loads(cached)
            order = self.store.get(order_id)
            if order is not None:
                self.cache.setex(key, self.ttl, json.dumps(order))
            return order

    def put(self, order_id, status):
        if not isinstance(status, str) or not status.strip() or len(status) > 80:
            raise ValueError("status must be a nonempty string of at most 80 characters")
        with self.lock:
            order = self.store.put(order_id, status.strip())
            self.cache.delete(f"order:{order_id}")
            return order

