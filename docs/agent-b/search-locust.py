import uuid

import jwt
from locust import HttpUser, between, task


class SearchUser(HttpUser):
    wait_time = between(4, 5)

    def on_start(self):
        self.client.headers["Authorization"] = "Bearer " + jwt.encode(
            {"sub": str(uuid.uuid4())},
            "controlled-fixture-key-for-tests-only-32",
            algorithm="HS256",
        )

    @task
    def search(self):
        with self.client.get(
            "/jobs/catalog?role=Python&location=Remote&limit=25", catch_response=True
        ) as response:
            if response.status_code == 200:
                payload = response.json()
                if len(payload["jobs"]) != 25 or not payload["next_cursor"]:
                    response.failure("Missing ranked jobs or cursor")
            else:
                response.failure(f"HTTP {response.status_code}")
