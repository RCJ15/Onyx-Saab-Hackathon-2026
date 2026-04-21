from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.infrastructure.api.dependencies import get_active_settings_or_bootstrap
from src.infrastructure.api.routes import (
    attack_plans,
    defense_playbooks,
    evaluation,
    knowledge,
    settings as settings_routes,
    training,
)
from src.infrastructure.persistence.database import init_db


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app() -> FastAPI:
    app = FastAPI(
        title="Boreal Passage Simulation Engine",
        version="2.0.0",
    )
    # NOTE: `allow_origins=["*"]` is invalid when `allow_credentials=True` — browsers
    # reject the response. Use an explicit origin list (override via CORS_ALLOW_ORIGINS).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(settings_routes.router, prefix="/api/v1")
    app.include_router(attack_plans.router, prefix="/api/v1")
    app.include_router(defense_playbooks.router, prefix="/api/v1")
    app.include_router(evaluation.router, prefix="/api/v1")
    app.include_router(training.router, prefix="/api/v1")
    app.include_router(knowledge.router, prefix="/api/v1")

    @app.on_event("startup")
    def startup():
        init_db()
        # Bootstrap: ensure there's at least one Settings row, active.
        try:
            get_active_settings_or_bootstrap()
        except Exception as e:
            print(f"Bootstrap warning: {e}")

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "2.0.0"}

    return app


app = create_app()
