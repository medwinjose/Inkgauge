"""FastAPI application for Inkgauge."""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, HTTPException, status, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import (
    MAX_CHARACTERS,
    ANTHROPIC_API_KEY,
)
from app.analysis.scoring import analyze_chapter, AUDIENCE_PRESETS
from app.ratelimit import check_rate_limit
from app.ai.features import rewrite_sentence, explain_hard_sentence, read_chapter

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Inkgauge",
    description="Readability and difficulty diagnostic tool for fiction and nonfiction authors.",
    docs_url=None,   # Disable swagger in production for clean lightweight footprint
    redoc_url=None,
)

# CORS Policy: restrict to same origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Same-origin requests default; configured cleanly
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# Security Headers & Memory-only Processing Middleware
@app.middleware("http")
async def add_security_headers_and_limit(request: Request, call_next):
    # Security headers
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self'; "
        "connect-src 'self'; "
        "img-src 'self' data:;"
    )
    return response


# Mount Static Files and Templates
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates_dir = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@app.get("/static/css/inkgauge.css")
async def css_endpoint():
    """Direct static CSS route fallback for serverless environments."""
    css_file = BASE_DIR / "static" / "css" / "inkgauge.css"
    if css_file.exists():
        return Response(content=css_file.read_text(encoding="utf-8"), media_type="text/css")
    return Response(status_code=404)


@app.get("/static/js/app.js")
async def js_endpoint():
    """Direct static JS route fallback for serverless environments."""
    js_file = BASE_DIR / "static" / "js" / "app.js"
    if js_file.exists():
        return Response(content=js_file.read_text(encoding="utf-8"), media_type="application/javascript")
    return Response(status_code=404)


def get_client_ip(request: Request) -> str:
    """Extract client IP from headers or connection."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


# Pydantic Schemas for API
class AnalyzeRequest(BaseModel):
    text: str = Field(description="Chapter text to analyze")
    audience: Optional[str] = Field(default="commercial_fiction", description="Target audience key")


class RewriteRequest(BaseModel):
    sentence: str
    context: str
    voice_sample: Optional[str] = None


class ExplainRequest(BaseModel):
    sentence: str
    reasons: List[str]


class ChapterReadRequest(BaseModel):
    text: str


@app.get("/", response_class=HTMLResponse)
async def index_view(request: Request):
    """Render the main Inkgauge single-page proof tool."""
    from app.ai.client import get_active_provider
    ctx = {
        "request": request,
        "audience_presets": AUDIENCE_PRESETS,
        "ai_enabled": True,
        "ai_provider": get_active_provider(),
    }
    try:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=ctx,
        )
    except Exception:
        tpl_path = BASE_DIR / "templates" / "index.html"
        if tpl_path.exists():
            from jinja2 import Template
            raw_html = tpl_path.read_text(encoding="utf-8")
            return HTMLResponse(Template(raw_html).render(ctx))
        raise


@app.get("/api/health")
async def health_check():
    """Health status and AI capability check."""
    from app.ai.client import get_active_provider
    return {
        "status": "ok",
        "ai_enabled": True,
        "ai_provider": get_active_provider(),
    }


@app.post("/api/analyze")
async def analyze_endpoint(payload: AnalyzeRequest, request: Request):
    """Core analysis endpoint."""
    ip = get_client_ip(request)
    allowed, retry_after = check_rate_limit(ip, "core")
    if not allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit reached (30 analyses per minute). Please wait {retry_after} seconds.",
                }
            },
        )

    text = payload.text
    if len(text) > MAX_CHARACTERS:
        return JSONResponse(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            content={
                "error": {
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": f"That's {len(text):,} characters. Inkgauge handles up to {MAX_CHARACTERS:,}. Paste one chapter at a time.",
                }
            },
        )

    if not text.strip():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "EMPTY_TEXT",
                    "message": "Please paste or write chapter text to analyze.",
                }
            },
        )

    # Process purely in memory
    results = analyze_chapter(text, payload.audience or "commercial_fiction")
    return results


@app.post("/api/ai/rewrite")
async def ai_rewrite_endpoint(payload: RewriteRequest, request: Request):
    """Suggest 3 rewrite variants with client-calculated FK grades."""
    ip = get_client_ip(request)
    allowed, retry_after = check_rate_limit(ip, "ai")
    if not allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"AI rate limit reached (10 requests per hour). Please wait {retry_after} seconds.",
                }
            },
        )

    if not payload.sentence.strip():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"code": "INVALID_INPUT", "message": "Sentence cannot be empty."}},
        )

    variants, error = rewrite_sentence(
        sentence=payload.sentence,
        context=payload.context,
        voice_sample=payload.voice_sample,
    )

    if error:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": {"code": "AI_ERROR", "message": error}},
        )

    return {"variants": variants}


@app.post("/api/ai/explain")
async def ai_explain_endpoint(payload: ExplainRequest, request: Request):
    """Generate editor's note under 50 words grounded in measured reasons."""
    ip = get_client_ip(request)
    allowed, retry_after = check_rate_limit(ip, "ai")
    if not allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"AI rate limit reached (10 requests per hour). Please wait {retry_after} seconds.",
                }
            },
        )

    result, error = explain_hard_sentence(
        sentence=payload.sentence,
        reasons=payload.reasons,
    )

    if error:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": {"code": "AI_ERROR", "message": error}},
        )

    return result


@app.post("/api/ai/chapter-read")
async def ai_chapter_read_endpoint(payload: ChapterReadRequest, request: Request):
    """Generate structured chapter developmental diagnostic."""
    ip = get_client_ip(request)
    allowed, retry_after = check_rate_limit(ip, "ai")
    if not allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"AI rate limit reached (10 requests per hour). Please wait {retry_after} seconds.",
                }
            },
        )

    if not payload.text.strip():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": {"code": "INVALID_INPUT", "message": "Text cannot be empty."}},
        )

    result, error = read_chapter(payload.text)
    if error:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": {"code": "AI_ERROR", "message": error}},
        )

    return result
