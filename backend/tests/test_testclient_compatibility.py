from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_testclient_can_dispatch_to_asgi_app() -> None:
    app = FastAPI()

    @app.get("/")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
