import pytest
from main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def test_right_location(client):
    locality = "Islamabad"
    locationName = "Pakistan"
    response = client.post(
        "/location_mapping", json={"locality": locality, "locationName": locationName}
    )
    assert "Asia" in response.json()["location_continent"]


def test_wrong_location(client):
    locality = "zxcvbnm"
    locationName = "qwertyuiop"
    response = client.post(
        "/location_mapping", json={"locality": locality, "locationName": locationName}
    )
    assert response.json()["location_continent"] == None


def test_for_multiple_continents(client):
    locality = "Moscow"
    locationName = "Russia"
    response = client.post(
        "/location_mapping", json={"locality": locality, "locationName": locationName}
    )
    assert (
        "Europe" in response.json()["location_continent"]
        and "Asia" in response.json()["location_continent"]
    )
