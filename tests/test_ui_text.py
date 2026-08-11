from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


STATIC = Path("app/static")


def test_static_ui_text_is_utf8_and_not_mojibake():
    expected_phrases = [
        "Não conformidades",
        "Próxima",
        "Alterações",
        "Inventário",
        "Diretórios",
        "Certificados",
        "Política e Objetivos da Qualidade",
    ]
    combined = "\n".join((STATIC / name).read_text(encoding="utf-8") for name in ["index.html", "app.js", "styles.css"])
    for marker in ["Ã", "ï¿½", "�"]:
        assert marker not in combined
    lower_combined = combined.lower()
    for phrase in expected_phrases:
        assert phrase.lower() in lower_combined


def test_health_exposes_maintenance_mode_disabled_by_default():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["maintenance_mode"] is False
