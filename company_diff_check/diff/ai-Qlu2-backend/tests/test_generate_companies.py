from fastapi.testclient import TestClient
import pytest
from main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def test_generate_companies(client):
    response = client.post(
        "/generatecompanies",
        json={"current_prompt": "Hospitality and leisure companies", "agent": "dual"},
    )

    assert len(response.text.split("\n")) > 1
