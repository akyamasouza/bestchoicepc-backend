from fastapi.testclient import TestClient

from app.main import app


class FakeDatabase:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def command(self, name: str) -> dict[str, int]:
        self.commands.append(name)
        return {"ok": 1}


def test_health_live_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready_pings_database(monkeypatch) -> None:
    fake_database = FakeDatabase()
    monkeypatch.setattr("app.main.get_database", lambda: fake_database)
    client = TestClient(app)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert fake_database.commands == ["ping"]
