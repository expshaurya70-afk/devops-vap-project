from fastapi.testclient import TestClient
from unittest.mock import patch
import httpx
from main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200


@patch("httpx.AsyncClient.get")
def test_create_order_valid_user(mock_get):
    mock_response = httpx.Response(200, json={"id": 1, "name": "Test", "email": "t@example.com"}, request=httpx.Request("GET", "http://users-service:8001/users/1"))
    mock_get.return_value = mock_response

    response = client.post("/orders", json={"user_id": 1, "item": "Laptop", "quantity": 1})
    assert response.status_code == 201


@patch("httpx.AsyncClient.get")
def test_create_order_invalid_user(mock_get):
    mock_response = httpx.Response(404)
    mock_get.return_value = mock_response

    response = client.post("/orders", json={"user_id": 999, "item": "Phone", "quantity": 1})
    assert response.status_code == 400
