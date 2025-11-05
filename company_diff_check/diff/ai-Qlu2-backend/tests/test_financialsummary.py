import pytest
from main import app
from .misc import financial_summary_payload
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def test_positive(client):
    financial_summary_payload["id"] = "apple"
    response = client.post("/companydata/summary", json=financial_summary_payload)
    response = response.json()
    flag = True
    for key, value in response.items():
        if value is None:
            flag = False
    assert len(response["output"]) > 0 and flag == True
