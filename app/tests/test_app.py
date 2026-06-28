import os

import pytest

os.environ["LOG_DIR"] = "logs/test"

from app import app


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    return app.test_client()


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "healthy"}


def test_dynamic_hello_route(client):
    response = client.get("/hello/student")

    assert response.status_code == 200
    assert response.get_json()["message"] == "Hello, student!"


def test_feedback_form_post(client):
    response = client.post("/feedback", data={"name": "Zura", "message": "Looks good"})

    assert response.status_code == 201
    assert response.get_json()["status"] == "received"


def test_feedback_requires_name_and_message(client):
    response = client.post("/feedback", data={"name": "", "message": ""})

    assert response.status_code == 400
