import pytest
from main import app
from .misc import rank_profiles_payload
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def test_rank_counts(client):
    response = client.post("/ranks/rank_counts", json={"universal_name": "microsoft"})
    response = response.json()
    assert response["output"]["C-suites"] > 0


def test_rank_profiles(client):
    response = client.post("/ranks/rank_profiles", json=rank_profiles_payload)
    response = response.json()
    assert len(response["output"]) > 0
