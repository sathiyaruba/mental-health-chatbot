from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

from app.config import settings
from app.database import create_tables
from app.routers import auth, chat, mood, contacts, therapist, users, admin

# ─── App Init ───────────────────────────────
app = FastAPI(
    title       = "Solace Mental Health API",
    description = "Backend for the Solace AI-powered mental health support platform",
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# ─── CORS ───────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = False,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ─── Routers (prefixes defined inside each router file) ─────
app.include_router(auth.router)        # /api/auth/*
app.include_router(chat.router)        # /api/chat/*
app.include_router(mood.router)        # /api/mood/*
app.include_router(contacts.router)    # /api/contacts/*
app.include_router(therapist.router)   # /api/therapists/*
app.include_router(users.router)       # /api/users/*
app.include_router(admin.router)        # /api/admin/*

# ─── Startup ────────────────────────────────
@app.on_event("startup")
def on_startup():
    create_tables()
    print("🌙 Solace backend started. Tables ready.")


# ─── Health Check ───────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}

@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}


# ─── Admin Panel HTML ───────────────────────
@app.get("/admin", response_class=HTMLResponse, tags=["Admin"])
def admin_panel():
    # Serve admin panel HTML file
    admin_path = os.path.join(os.path.dirname(__file__), "..", "admin.html")
    if os.path.exists(admin_path):
        with open(admin_path, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("<h1>Admin panel not found. Place admin.html in solace-backend folder.</h1>", status_code=404)


# ─── Global Error Handler ───────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code = 500,
        content     = {"detail": "Internal server error", "error": str(exc)},
    )