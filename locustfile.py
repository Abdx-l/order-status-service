from locust import HttpUser, between, task


class OrderTraffic(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(9)
    def read(self):
        self.client.get("/orders/1")

    @task(1)
    def write(self):
        self.client.put("/orders/1", json={"status": "processing"})

