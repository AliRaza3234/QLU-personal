# from fastapi.testclient import TestClient
# import asyncio

# from main import app

# client = TestClient(app)


# def test_suggest_term_input_payload():
#     response = client.post(
#         "/suggest-terms", json={"entity": "LOL", "entity_type": "LOL"}
#     )
#     assert "locations" in response.text


# def test_read_main():
#     response = client.get("/")
#     assert response.status_code == 200
#     assert response.json() == {"message": "OK"}


# def test_suggest_terms():
#     response = client.post(
#         "/suggest-terms",
#         json={
#             "entity": "chief operations & financial officer",
#             "entity_type": "titles",
#         },
#     )
#     print(response.json())
#     assert "chief financial officer" in [i.lower() for i in response.json()]
#     assert response.status_code == 200


# def test_hvac_industry():
#     response = client.post(
#         "/suggest-terms", json={"entity": "heating", "entity_type": "industries"}
#     )
#     assert "Energy Efficiency" in [i for i in response.json()]
#     assert response.status_code == 200


# def test_cache_industry():
#     response = client.post(
#         "/suggest-terms", json={"entity": "mobile deviceS", "entity_type": "industries"}
#     )
#     # assert "Energy Efficiency" in [i for i in response.json()]
#     assert response.status_code == 200

#     from qutils.caching import get_cached_data
#     import time

#     time.sleep(3)

#     assert "gpt-3.5-turbo" in asyncio.run(
#         get_cached_data("v2-suggest-terms~industries~mobile devices")
#     )


# def test_degrees():
#     response = client.post(
#         "/suggest-terms",
#         json={"entity": "Bachelor's in Mechatronics", "entity_type": "degrees"},
#     )
#     assert response.status_code == 200
#     assert len([i for i in response.json() if "mechanical" in i.lower()]) > 0
