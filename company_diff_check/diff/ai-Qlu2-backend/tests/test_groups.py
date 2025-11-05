import pytest
from main import app
from .misc import (
    groups_subgroup_counts_payload,
    groups_subgroup_rank_counts_payload,
    groups_subgroup_function_counts_payload,
    group_subgroups_ranks_profiles_payload,
    group_subgroups_functions_profiles_payload,
)
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def test_subgroup_counts_test_case(client):
    response = client.post(
        "/groups/subgroup_counts", json=groups_subgroup_counts_payload
    )
    response = response.json()
    assert response["output"]["Gaming"]["Xbox"] > 0


def test_subgroup_rank_counts_test_case(client):
    response = client.post(
        "/groups/subgroup_rank_function_counts",
        json=groups_subgroup_rank_counts_payload,
    )
    response = response.json()
    assert response["output"]["Directors"] > 0


def test_subgroup_function_counts_test_case(client):
    response = client.post(
        "/groups/subgroup_rank_function_counts",
        json=groups_subgroup_function_counts_payload,
    )
    response = response.json()
    assert response["output"]["Sales"] > 0


def test_subgroup_ranks_profiles_test_case(client):
    response = client.post(
        "/groups/subgroup_rank_function_profiles",
        json=group_subgroups_ranks_profiles_payload,
    )
    response = response.json()
    assert len(response["output"]) > 0


def test_subgroup_functions_profiles_test_case(client):
    response = client.post(
        "/groups/subgroup_rank_function_profiles",
        json=group_subgroups_functions_profiles_payload,
    )
    response = response.json()
    assert len(response["output"]) > 0
