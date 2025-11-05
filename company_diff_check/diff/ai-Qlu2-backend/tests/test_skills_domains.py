# from fastapi.testclient import TestClient
# from .misc import person_domains, person_skills
# from main import app

# client = TestClient(app)

# def test_generate_skills():
#     result = client.post("/generate-skills-domains", json=person_skills)
#     result = result.json()
#     assert "Financial Controlling" in result.keys()


# def test_domains_generation():
#     result = client.post("/generate-skills-domains", json=person_domains)
#     result = result.json()
#     assert "Artificial Intelligence" in result.keys()
