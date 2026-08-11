from fastapi.testclient import TestClient

from app.main import app


def test_health_and_dashboard():
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        dashboard = client.get("/api/v1/dashboard/summary")
        assert dashboard.status_code == 200
        assert "needs_attention" in dashboard.json()


def test_assistant_always_returns_sources_structure():
    with TestClient(app) as client:
        response = client.post("/api/v1/assistant/query", json={"question": "Quais certificados estão vencidos?"})
        assert response.status_code == 200
        payload = response.json()
        assert "answer" in payload
        assert "sources" in payload
        assert "confirmation_needed" in payload


def test_documents_endpoint_is_paginated():
    with TestClient(app) as client:
        response = client.get("/api/v1/documents?page=1&page_size=25")
        assert response.status_code == 200
        payload = response.json()
        assert set(payload) == {"items", "page", "page_size", "total_items", "total_pages"}
        assert payload["page"] == 1
        assert payload["page_size"] == 25
        assert len(payload["items"]) <= 25


def test_documents_endpoint_filters_and_sorts():
    with TestClient(app) as client:
        response = client.get("/api/v1/documents?page=1&page_size=10&extension=.txt&sort_by=name&sort_direction=asc")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload["items"]) <= 10
        assert all(item["extension"] == ".txt" for item in payload["items"])
