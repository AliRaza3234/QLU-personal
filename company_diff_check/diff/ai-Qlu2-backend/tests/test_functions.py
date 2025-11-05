import pytest
from main import app
from .misc import function_profiles_payload
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def test_function_counts(client):
    response = client.post(
        "/functions/function_counts", json={"universal_name": "microsoft"}
    )
    response = response.json()
    assert response["output"]["Sales"] > 0


def test_function_profiles(client):
    response = client.post(
        "/functions/function_profiles", json=function_profiles_payload
    )
    response = response.json()
    assert len(response["output"]) > 0
