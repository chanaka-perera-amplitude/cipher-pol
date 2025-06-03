import pytest
from httpx import AsyncClient, ASGITransport # Import ASGITransport
from fastapi import FastAPI, status
from api.health import router as health_router


@pytest.fixture
def test_app_with_health_router() -> FastAPI:
    """
    Fixture to create a FastAPI app instance with only the health_router included.
    This allows for more isolated testing of the health router.
    """
    app = FastAPI(
        title="Test App for Health Router",
        description="A minimal app to test the health router.",
        version="0.1.0-test",
    )
    app.include_router(health_router)
    return app

@pytest.mark.asyncio # Changed back to asyncio
async def test_health_check_via_isolated_router(test_app_with_health_router: FastAPI):
    """
    Test the health check endpoint by directly using an app with only the health_router.
    It should return a 200 OK status and the correct health status message.
    """
    transport = ASGITransport(app=test_app_with_health_router)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        response = await ac.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy", "message": "Service is up and running!"}

@pytest.mark.asyncio # Changed back to asyncio
async def test_health_check_status_explicit_via_isolated_router(test_app_with_health_router: FastAPI):
    """
    Test that the health check endpoint explicitly returns HTTP_200_OK
    when tested via the isolated router.
    """
    transport = ASGITransport(app=test_app_with_health_router)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        response = await ac.get("/health")
    assert response.status_code == status.HTTP_200_OK
