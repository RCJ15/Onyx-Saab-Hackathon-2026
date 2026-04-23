from __future__ import annotations

from fastapi import APIRouter, HTTPException

from sqlalchemy import text

from src.infrastructure.api.dependencies import get_settings_uc, get_kb
from src.infrastructure.persistence.database import get_session
from src.infrastructure.api.schemas import (
    CreateSettingsFromScenarioRequest,
    SettingsResponse,
)


router = APIRouter(prefix="/settings", tags=["settings"])


def _to_response(settings, active_id: str | None) -> SettingsResponse:
    return SettingsResponse(
        settings_id=settings.settings_id,
        name=settings.name,
        tick_minutes=settings.tick_minutes,
        max_ticks=settings.max_ticks,
        created_at=settings.created_at,
        notes=settings.notes,
        is_active=(settings.settings_id == active_id),
    )


@router.get("")
def list_settings():
    uc = get_settings_uc()
    active = uc.get_active()
    active_id = active.settings_id if active else None
    return {
        "settings": [_to_response(s, active_id).model_dump() for s in uc.list_all()],
        "active_id": active_id,
    }


@router.get("/active")
def get_active():
    uc = get_settings_uc()
    active = uc.get_active()
    if not active:
        raise HTTPException(404, "No active settings")
    return _to_response(active, active.settings_id).model_dump() | {
        "scenario": active.scenario,
        "defender_resources": active.defender_resources,
        "attacker_resources": active.attacker_resources,
        "engagement_params": active.engagement_params,
    }


@router.get("/{settings_id}")
def get_settings(settings_id: str):
    uc = get_settings_uc()
    s = get_kb().settings.get(settings_id)
    if not s:
        raise HTTPException(404, "Settings not found")
    active = uc.get_active()
    active_id = active.settings_id if active else None
    return _to_response(s, active_id).model_dump() | {
        "scenario": s.scenario,
        "defender_resources": s.defender_resources,
        "attacker_resources": s.attacker_resources,
        "engagement_params": s.engagement_params,
    }


@router.post("/from-scenario")
def create_from_scenario(req: CreateSettingsFromScenarioRequest):
    uc = get_settings_uc()
    settings = uc.create_from_scenario_json(
        name=req.name,
        scenario_path=req.scenario_path,
        notes=req.notes,
    )
    active = uc.get_active()
    active_id = active.settings_id if active else None
    return _to_response(settings, active_id).model_dump()


@router.post("/{settings_id}/activate")
def activate(settings_id: str):
    uc = get_settings_uc()
    s = get_kb().settings.get(settings_id)
    if not s:
        raise HTTPException(404, "Settings not found")
    uc.set_active(settings_id)
    return {"activated": settings_id}


@router.delete("/{settings_id}")
def delete_settings(settings_id: str):
    uc = get_settings_uc()
    if not uc.delete(settings_id):
        raise HTTPException(404, "Settings not found")
    return {"deleted": settings_id}


@router.post("/reset-all")
def reset_all():
    """Wipe every table in the database. Irreversible."""
    _TABLES = [
        "evaluation_conversations",
        "training_jobs",
        "doctrine_entries",
        "match_results",
        "defense_playbooks",
        "attack_patterns",
        "attack_plans",
        "settings",
    ]
    session = get_session()
    try:
        for table in _TABLES:
            session.execute(text(f"DELETE FROM {table}"))
        session.commit()
    finally:
        session.close()
    return {"reset": True}
