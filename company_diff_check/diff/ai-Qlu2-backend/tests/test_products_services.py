import pytest
from main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def test_products_search(client):
    response = client.post("/companydata/products", json={"universalName": "apple"})
    results = response.json()
    assert len(results["products"]) > 0
