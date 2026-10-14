"""API integration tests covering all routes, error cases, limits, and mocked AI."""

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ratelimit import reset_rate_limits
from app.config import MAX_CHARACTERS

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_rate_limits():
    """Ensure clean rate limits between test runs."""
    reset_rate_limits()
    yield
    reset_rate_limits()


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["ai_enabled"] is True
    assert "ai_provider" in data


def test_security_headers():
    response = client.get("/")
    assert response.status_code == 200
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_analyze_valid_text_and_offset_integrity():
    text = (
        "Captain Miller stepped into the rain. "
        "The dark alley smelled of salt and decaying wood. "
        "'Wait here,' he whispered to Chen. "
        "Chen nodded and gripped the rusted iron banister. "
        "Nothing stirred in the silence of the docks."
    )
    response = client.post("/api/analyze", json={"text": text, "audience": "commercial_fiction"})
    assert response.status_code == 200
    data = response.json()

    assert "reading_ease" in data
    assert "grade_level" in data
    assert "hardest_sentences" in data
    assert "paragraphs" in data
    assert "style_flags" in data

    # Verify offset test through API
    for s in data["hardest_sentences"]:
        start = s["start"]
        end = s["end"]
        extracted = text[start:end]
        assert extracted == s["text"], f"Offset failed: '{extracted}' != '{s['text']}'"

    for p in data["paragraphs"]:
        for s in p["sentences"]:
            start = s["start"]
            end = s["end"]
            assert text[start:end] == s["text"]


def test_analyze_empty_text():
    response = client.post("/api/analyze", json={"text": "   "})
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "EMPTY_TEXT"


def test_analyze_exceeds_character_limit():
    huge_text = "a" * (MAX_CHARACTERS + 10)
    response = client.post("/api/analyze", json={"text": huge_text})
    assert response.status_code == 413
    data = response.json()
    assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert "Inkgauge handles up to 150,000" in data["error"]["message"]


def test_analyze_rate_limiting():
    # 30 allowed, 31st returns 429
    text = "Short valid sentence for testing rate limits."
    for _ in range(30):
        res = client.post("/api/analyze", json={"text": text})
        assert res.status_code == 200

    exceeded = client.post("/api/analyze", json={"text": text})
    assert exceeded.status_code == 429
    assert exceeded.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


@patch("app.ai.client._call_anthropic_json")
def test_ai_rewrite_mocked_anthropic(mock_call):
    mock_call.return_value = '{"lighter": "Miller waited.", "balanced": "Miller waited quietly by the docks.", "voice_preserving": "Captain Miller stepped into the cold rain."}'

    with patch("app.ai.client.ANTHROPIC_API_KEY", "mock-key"):
        response = client.post(
            "/api/ai/rewrite",
            json={
                "sentence": "Captain Miller stepped into the torrential downpour outside.",
                "context": "Paragraph context around the sentence.",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "variants" in data
        assert "lighter" in data["variants"]
        assert "balanced" in data["variants"]
        assert "voice_preserving" in data["variants"]
        assert "grade" in data["variants"]["lighter"]


def test_ai_local_engine_runs_without_api_keys():
    """Verify that all AI endpoints succeed cleanly using the free local engine with zero keys."""
    with patch("app.ai.client.ANTHROPIC_API_KEY", ""), patch("app.ai.client.GEMINI_API_KEY", ""):
        # 1. Rewrite
        resp_rewrite = client.post(
            "/api/ai/rewrite",
            json={
                "sentence": "The organizational methodology was systematically hindered by legacy infrastructure deficiencies.",
                "context": "A long dense paragraph about business reorganization.",
            },
        )
        assert resp_rewrite.status_code == 200
        data_rewrite = resp_rewrite.json()
        assert "variants" in data_rewrite
        assert data_rewrite["variants"]["provider"] == "local"
        assert len(data_rewrite["variants"]["lighter"]["text"]) > 0
        assert data_rewrite["variants"]["lighter"]["grade"] >= 0

        # 2. Explain
        resp_explain = client.post(
            "/api/ai/explain",
            json={
                "sentence": "The organizational methodology was systematically hindered by legacy infrastructure deficiencies.",
                "reasons": ["Passive voice: 'was systematically hindered'.", "Four words of 3+ syllables."],
            },
        )
        assert resp_explain.status_code == 200
        data_explain = resp_explain.json()
        assert "editor_note" in data_explain
        assert data_explain["provider"] == "local"

        # 3. Chapter Read
        resp_read = client.post(
            "/api/ai/chapter-read",
            json={
                "text": "First paragraph of chapter.\n\nSecond dense paragraph with lots of long words and clauses.\n\nThird paragraph concluding."
            },
        )
        assert resp_read.status_code == 200
        data_read = resp_read.json()
        assert "pacing" in data_read
        assert "clarity" in data_read
        assert data_read["provider"] == "local"
        assert len(data_read["stall_points"]) >= 1


@patch("app.ai.client._call_gemini_json")
def test_ai_gemini_integration_mocked(mock_gemini):
    mock_gemini.return_value = '{"editor_note": "A clear note generated via Google Gemini free tier."}'

    with patch("app.ai.client.ANTHROPIC_API_KEY", ""), patch("app.ai.client.GEMINI_API_KEY", "mock-gemini-key"):
        response = client.post(
            "/api/ai/explain",
            json={
                "sentence": "A test sentence for Gemini.",
                "reasons": ["Sample reason"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["editor_note"] == "A clear note generated via Google Gemini free tier."
        assert data["provider"] == "gemini"


def test_serverless_path_normalization_get():
    """Verify that requests routed to /api/index.py?__path=/api/health resolve correctly."""
    response = client.get("/api/index.py?__path=/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["ai_enabled"] is True


def test_serverless_path_normalization_post():
    """Verify that POST requests routed to /api/index.py?__path=/api/analyze resolve without 405."""
    response = client.post(
        "/api/index.py?__path=/api/analyze",
        json={"text": "Captain Miller stepped into the rain. The dark alley smelled of salt.", "audience": "commercial_fiction"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "hardest_sentences" in data
    assert "reading_ease" in data


def test_static_endpoints():
    """Verify that static fallback routes return appropriate CSS and JS media types."""
    css_resp = client.get("/static/css/inkgauge.css")
    assert css_resp.status_code == 200
    assert "text/css" in css_resp.headers["content-type"]
    assert "font-family" in css_resp.text or "color" in css_resp.text

    js_resp = client.get("/static/js/app.js")
    assert js_resp.status_code == 200
    assert "javascript" in js_resp.headers["content-type"]
    assert "addEventListener" in js_resp.text or "function" in js_resp.text


def test_head_requests():
    """Verify that HEAD requests on health and root endpoints succeed."""
    assert client.head("/api/health").status_code == 200
    assert client.head("/").status_code == 200
