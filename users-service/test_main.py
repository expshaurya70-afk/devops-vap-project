from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "okay"}


def test_create_and_get_user():
    response = client.post("/users", json={"name": "Test User", "email": "test@example.com"})
    assert response.status_code == 201
    user_id = response.json()["id"]

    response = client.get(f"/users/{user_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Test User"


def test_get_nonexistent_user():
    response = client.get("/users/999999")
    assert response.status_code == 404


def test_delete_user():
    create = client.post("/users", json={"name": "Delete Me", "email": "delete@example.com"})
    user_id = create.json()["id"]

    response = client.delete(f"/users/{user_id}")
    assert response.status_code == 204

    response = client.get(f"/users/{user_id}")
    assert response.status_code == 404
