import pytest
from main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def test_basic(client):
    response = client.post(
        "/autocomplete", json={"uncomplete_entity": "vp", "entity_type": "job titles"}
    )
    assert (
        len([i for i in response.json()["entity_list"] if "finance" in i.lower()]) == 1
    )
    assert response.status_code == 200


def test_empty(client):
    response = client.post(
        "/autocomplete",
        json={"uncomplete_entity": "zxcvbnm", "entity_type": "industries"},
    )
    assert len(response.json()["entity_list"]) == 0


def test_1_character(client):
    response = client.post(
        "/autocomplete", json={"uncomplete_entity": "m", "entity_type": "titles"}
    )
    assert len(response.json()) > 0


def test_3_character(client):
    response = client.post(
        "/autocomplete", json={"uncomplete_entity": "mac", "entity_type": "titles"}
    )
    assert len(response.json()) > 0


def test_long_string(client):
    response = client.post(
        "/autocomplete",
        json={
            "uncomplete_entity": "machine learning engineer",
            "entity_type": "titles",
        },
    )
    assert len(response.json()) >= 0
