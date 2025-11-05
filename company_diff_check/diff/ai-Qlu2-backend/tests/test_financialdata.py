import pytest
from main import app
from .misc import financial_data_payload
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def test_yearly_income(client):
    financial_data_payload["id"] = "apple"
    financial_data_payload["financial_type"] = "incomestatement"
    financial_data_payload["type"] = "yearly"
    response = client.post("/companydata/financialdata", json=financial_data_payload)
    response = response.json()
    assert len(response["output"]) > 0


def test_quarterly_income(client):
    financial_data_payload["id"] = "apple"
    financial_data_payload["financial_type"] = "incomestatement"
    financial_data_payload["type"] = "quarterly"
    response = client.post("/companydata/financialdata", json=financial_data_payload)
    response = response.json()
    assert len(response["output"]) > 0


def test_yearly_cashflow(client):
    financial_data_payload["id"] = "apple"
    financial_data_payload["financial_type"] = "cashflow"
    financial_data_payload["type"] = "yearly"
    response = client.post("/companydata/financialdata", json=financial_data_payload)
    response = response.json()
    assert len(response["output"]) > 0


def test_quarterly_cashflow(client):
    financial_data_payload["id"] = "apple"
    financial_data_payload["financial_type"] = "cashflow"
    financial_data_payload["type"] = "quarterly"
    response = client.post("/companydata/financialdata", json=financial_data_payload)
    response = response.json()
    assert len(response["output"]) > 0
