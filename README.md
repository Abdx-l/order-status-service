# Order Status Service with Caching

An HTTP order service with read-through caching, 30-second expiry, and update invalidation. The local runner uses SQLite and an in-memory TTL cache, so it starts without external services. The repository also includes Redis and PostgreSQL adapters for deployed configurations and a Locust 90% read / 10% write profile.

```sh
python app.py --db orders.db
python -m unittest discover -s tests -v
```

`GET /orders/{id}` returns an order; `PUT /orders/{id}` accepts `{"status":"shipped"}`. Writes and cache updates use one process lock in the local runner to prevent stale cache fills during a concurrent write. That lock does not coordinate multiple workers. The optional Redis/PostgreSQL adapters require `redis` and `psycopg` and external services; those integrations have not been exercised against live instances.

