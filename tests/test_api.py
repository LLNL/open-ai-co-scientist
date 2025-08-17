import pytest
from fastapi.testclient import TestClient
from app.api import app, supervisor
import os

@pytest.fixture
def client():
    return TestClient(app)

def test_run_cycle_propagates_llm_error(client, monkeypatch):
    # Simulate a research goal being set
    client.post("/research_goal", json={"description": "test goal"})

    # Patch supervisor.run_cycle to simulate an LLM error
    def mock_run_cycle(research_goal, context):
        return {
            "iteration": 1,
            "steps": {"generation": {"hypotheses": []}},
            "errors": ["Authentication with OpenRouter failed (401 Unauthorized). Please check your API key."]
        }
    monkeypatch.setattr(supervisor, "run_cycle", mock_run_cycle)

    # Call /run_cycle and check for error propagation
    response = client.post("/run_cycle")
    assert response.status_code == 200
    data = response.json()
    assert "errors" in data
    assert any("OpenRouter" in err for err in data["errors"])

def test_tail_log_endpoint(client):
    # Prepare a test log file
    log_dir = "results"
    os.makedirs(log_dir, exist_ok=True)
    test_log_path = os.path.join(log_dir, "app_log_test.txt")
    lines = [f"line {i}\n" for i in range(1, 21)]
    with open(test_log_path, "w") as f:
        f.writelines(lines)

    # Patch glob to return only our test log file as the latest
    import glob as glob_module
    orig_glob = glob_module.glob
    def mock_glob(pattern):
        if "app_log_*.txt" in pattern:
            return [test_log_path]
        return orig_glob(pattern)
    glob_module.glob = mock_glob

    try:
        # Call the endpoint and check the last 5 lines
        response = client.get("/tail_log?lines=5")
        assert response.status_code == 200
        data = response.json()
        assert "log" in data
        for i in range(16, 21):
            assert f"line {i}" in data["log"]
    finally:
        # Clean up
        os.remove(test_log_path)
        glob_module.glob = orig_glob
