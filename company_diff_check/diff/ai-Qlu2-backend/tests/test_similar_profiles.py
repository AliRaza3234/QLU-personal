# import pytest
# from main import app
# from .misc import external_similar_profiles_payload, internal_similar_profiles_payload
# from fastapi.testclient import TestClient


# @pytest.fixture(scope="session")
# def client():
#     with TestClient(app) as c:
#         yield c


# def test_external_similar_profiles(client):
#     response = client.get(
#         f"/similar_profiles?esId={external_similar_profiles_payload['esId']}&type={external_similar_profiles_payload['type']}&offset={external_similar_profiles_payload['offset']}&limit={external_similar_profiles_payload['limit']}"
#     )
#     response_data = response.json()
#     output = response_data.get("output", [])
#     if output:
#         profiles = output[0]
#         assert len(profiles) >= 0
#     else:
#         assert False, "No profiles found in the output."


# def test_internal_similar_profiles(client):
#     response = client.get(
#         f"/similar_profiles?esId={internal_similar_profiles_payload['esId']}&type={internal_similar_profiles_payload['type']}&offset={internal_similar_profiles_payload['offset']}&limit={internal_similar_profiles_payload['limit']}"
#     )
#     response_data = response.json()

#     output = response_data.get("output", [])
#     if output:
#         profiles = output[0]
#         assert len(profiles) >= 0
#     else:
#         assert False, "No profiles found in the output."
