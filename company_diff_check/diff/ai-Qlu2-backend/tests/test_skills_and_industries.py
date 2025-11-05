import pytest
import httpx
from main import app
from fastapi.testclient import TestClient
from httpx import ASGITransport


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_skills_and_industry(client):
    payload = {
        "skills": ["Python", "Microsoft Office"],
        "industries": ["Pharmaceutical"],
    }

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/skills_industries", json=payload)
        result = response.json()
        assert len(result) == 2
