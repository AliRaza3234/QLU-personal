import pytest
from main import app
from .misc import stocks_payload
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def test_positive(client):
    stocks_payload["id"] = "apple"
    response = client.post("/companydata/stocks", json=stocks_payload)
    response = response.json()
    assert len(response["output"]) > 0 and "message" not in response["output"]


def test_negative(client):
    stocks_payload["id"] = "AApple"
    response = client.post("/companydata/stocks", json=stocks_payload)
    response = response.json()
    assert len(response) > 0 and "message" in response
