# from main import app
# from fastapi.testclient import TestClient
# from .misc import financials_payload_no_esid, financials_payload_esid

# client = TestClient(app)


# def test_without_es_id():
#     response = client.post(
#         "/financial_filters", json={"payload": financials_payload_no_esid}
#     )
#     response = response.json()
#     assert len(response["result"]) > 0


# def test_with_es_ids():
#     response = client.post(
#         "/financial_filters", json={"payload": financials_payload_esid}
#     )
#     response = response.json()
#     assert len(response["result"]) > 0
