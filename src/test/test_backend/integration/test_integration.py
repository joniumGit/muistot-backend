from fastapi.testclient import TestClient


def test_hello(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200


def test_projects(client: TestClient):
    resp = client.get("/projects")
    assert resp.status_code == 200


def test_lang(client: TestClient):
    resp = client.get("/languages?q=fi")
    assert resp.json() == {"id": "fin", "name": "Finnish"}
