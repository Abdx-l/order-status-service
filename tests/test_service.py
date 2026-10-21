import json
import tempfile
import threading
import unittest
from pathlib import Path
from service import MemoryCache, OrderService, SQLiteOrders


class CountingStore:
    def __init__(self, store):
        self.store, self.reads = store, 0
    def get(self, key):
        self.reads += 1
        return self.store.get(key)
    def put(self, key, status): return self.store.put(key, status)


class OrderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = CountingStore(SQLiteOrders(str(Path(self.tmp.name) / "orders.db")))
        self.addCleanup(self.store.store.connection.close)
        self.now = [0.]
        self.cache = MemoryCache(clock=lambda: self.now[0])
        self.service = OrderService(self.store, self.cache)

    def test_cache_expiry_and_invalidation(self):
        self.assertIsNone(self.service.get(1))
        self.service.put(1, "new")
        self.assertEqual(self.service.get(1)["status"], "new")
        self.assertEqual(self.service.get(1)["status"], "new")
        self.assertEqual(self.store.reads, 2)
        self.now[0] = 30
        self.assertEqual(self.service.get(1)["status"], "new")
        self.assertEqual(self.store.reads, 3)
        self.service.put(1, "shipped")
        self.assertEqual(self.service.get(1)["version"], 2)
        self.assertEqual(self.service.get(1)["status"], "shipped")

    def test_read_write_race(self):
        self.service.put(1, "new")
        errors = []
        def writer():
            for i in range(100):
                self.service.put(1, str(i))
        def reader():
            try:
                for _ in range(100):
                    result = self.service.get(1)
                    self.assertIsNotNone(result)
            except Exception as exc: errors.append(exc)
        a, b = threading.Thread(target=writer), threading.Thread(target=reader)
        a.start(); b.start(); a.join(); b.join()
        self.assertFalse(errors)
        self.assertEqual(self.service.get(1)["status"], "99")
        self.assertEqual(self.service.get(1)["version"], 101)

    def test_validation(self):
        with self.assertRaises(ValueError): self.service.put(1, "")
        with self.assertRaises(ValueError): self.service.put(1, "a" * 81)


if __name__ == "__main__": unittest.main()

