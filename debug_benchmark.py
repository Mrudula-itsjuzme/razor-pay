from fastapi.testclient import TestClient
from main import app
client = TestClient(app)
client.post("/api/demo")
res = client.post("/api/benchmark")
print(res.json()["metrics"]["exact"])
print(res.json()["metrics"]["proposed"])
