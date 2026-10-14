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


# Path Normalization Middleware for Serverless Entrypoints
@app.middleware("http")
async def normalize_serverless_path(request: Request, call_next):
    # 1. Check if Vercel passed the path via query parameter __path
    query_path = request.query_params.get("__path")
    if query_path:
        norm_path = query_path if query_path.startswith("/") else ("/" + query_path)
        request.scope["path"] = norm_path

        # Clean __path from query_string in ASGI scope so endpoints don't see it
        raw_qs = request.scope.get("query_string", b"").decode("latin-1")
        from urllib.parse import parse_qsl, urlencode
        clean_params = [(k, v) for k, v in parse_qsl(raw_qs, keep_blank_values=True) if k != "__path"]
        request.scope["query_string"] = urlencode(clean_params).encode("latin-1")
        return await call_next(request)

    # 2. Check if a proxy or Vercel passed the original path in headers
    for h in ("x-forwarded-path", "x-matched-path"):
        hdr_val = request.headers.get(h)
        if hdr_val and not hdr_val.startswith("/api/index"):
            request.scope["path"] = hdr_val if hdr_val.startswith("/") else ("/" + hdr_val)
            return await call_next(request)

    # 3. Strip any serverless file prefix (/api/index.py or /api/index)
    raw_path = request.scope.get("path", "")
    for prefix in ("/api/index.py", "/api/index"):
        if raw_path.startswith(prefix):
            remainder = raw_path[len(prefix):]
            request.scope["path"] = remainder if remainder.startswith("/") else (("/" + remainder) if remainder else "/")
            break

    return await call_next(request)


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
if not static_dir.exists():
    static_dir = BASE_DIR.parent / "public" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates_dir = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@app.get("/static/css/inkgauge.css")
async def css_endpoint():
    """Direct static CSS route fallback for serverless environments."""
    for p in (BASE_DIR / "static" / "css" / "inkgauge.css", BASE_DIR.parent / "public" / "static" / "css" / "inkgauge.css"):
        if p.exists():
            return Response(content=p.read_text(encoding="utf-8"), media_type="text/css")
    return Response(status_code=404)


@app.get("/static/js/app.js")
async def js_endpoint():
    """Direct static JS route fallback for serverless environments."""
    for p in (BASE_DIR / "static" / "js" / "app.js", BASE_DIR.parent / "public" / "static" / "js" / "app.js"):
        if p.exists():
            return Response(content=p.read_text(encoding="utf-8"), media_type="application/javascript")
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


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/api/index.py", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/api/index", methods=["GET", "HEAD"], response_class=HTMLResponse)
@app.api_route("/api", methods=["GET", "HEAD"], response_class=HTMLResponse)
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


@app.api_route("/api/health", methods=["GET", "HEAD"])
async def health_check():
    """Health status and AI capability check."""
    from app.ai.client import get_active_provider
    return {
        "status": "ok",
        "ai_enabled": True,
        "ai_provider": get_active_provider(),
    }


@app.get("/api/debug-path")
async def debug_path(request: Request):
    """Temporary debug endpoint to inspect ASGI scope on Vercel."""
    return {
        "scope_path": request.scope.get("path"),
        "scope_raw_path": request.scope.get("raw_path", b"").decode("utf-8", errors="replace"),
        "scope_root_path": request.scope.get("root_path", ""),
        "url": str(request.url),
        "headers_x_matched_path": request.headers.get("x-matched-path", ""),
        "headers_x-forwarded-path": request.headers.get("x-forwarded-path", ""),
        "headers_x-vercel-forwarded-for": request.headers.get("x-vercel-forwarded-for", ""),
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
