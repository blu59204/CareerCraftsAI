"""
Load test baseline for JobAgent AI API.
Run: locust --host=http://localhost:8000 --users=20 --spawn-rate=4 --run-time=30s --headless
Requires LOAD_TEST_TOKEN env var set to a valid Supabase access token.
"""
import os
from locust import HttpUser, task, between


class JobAgentUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        token = os.getenv("LOAD_TEST_TOKEN", "")
        self.client.headers.update({"Authorization": f"Bearer {token}"})

    @task(3)
    def health_check(self):
        self.client.get("/health")

    @task(2)
    def get_applications(self):
        self.client.get("/api/v1/jobs/applications")

    @task(2)
    def list_documents(self):
        self.client.get("/api/v1/rag/documents")

    @task(1)
    def get_me(self):
        self.client.get("/api/v1/users/me")
