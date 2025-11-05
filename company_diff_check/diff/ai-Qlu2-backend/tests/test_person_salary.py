# import sys
# import os
# import asyncio

# from fastapi.testclient import TestClient

# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# from main import app

# from app.utils.salary_data.rapid_api import RapidApi
# from app.utils.salary_data.glassdoor_salary import get_glassdoor_salary
# from app.utils.salary_data.salary_com_original import executive_salaries

# client = TestClient(app)


# def test_products_search():
#     response = client.post("/person_salary", json={"esId": "924300"})
#     results = response.json()
#     assert len(results["result"]) == 5


# def test_rapid_api():
#     data = asyncio.run(
#         RapidApi("Apple", "Software Engineer", "United States", 2000, None, CACHE=False)
#     )
#     assert (data != None) and (type(data[0]) == float)


# def test_glassdoor():
#     data = asyncio.run(
#         get_glassdoor_salary("Software Engineer", None, "United States", CACHE=False)
#     )
#     assert (data != None) and (type(data[0]) == float)


# def test_executive_salary():
#     data = asyncio.run(executive_salaries("Tim Cook", "Apple", "apple"))
#     years = data[0].keys()
#     assert 2022 in years
