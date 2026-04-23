from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from src.infrastructure.api.dependencies import (
    get_active_settings_or_bootstrap,
    get_kb,
)
from src.infrastructure.api.schemas import RenameDoctrineRequest


router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _counts(kb, settings_id: str) -> dict:
    return {
        "attack_plans": kb.attack_plans.count_by_settings(settings_id),
        "attack_patterns": kb.attack_patterns.count_by_settings(settings_id),
        "defense_playbooks": kb.defense_playbooks.count_by_settings(settings_id),
        "match_results": kb.match_results.count_by_settings(settings_id),
        "doctrine_entries": kb.doctrine.count_active_by_settings(settings_id),
    }


@router.get("/summary")
def summary():
    settings = get_active_settings_or_bootstrap()
    kb = get_kb()
    return {
        "settings_id": settings.settings_id,
        "settings_name": settings.name,
        "counts": _counts(kb, settings.settings_id),
    }


@router.get("/doctrine")
def list_doctrine(category: str | None = None):
    settings = get_active_settings_or_bootstrap()
    kb = get_kb()
    entries = kb.doctrine.list_active(settings.settings_id, category=category)
    return {
        "entries": [e.to_dict() for e in entries],
        "total": len(entries),
    }


@router.patch("/doctrine/{entry_id}/name")
def rename_doctrine(entry_id: str, body: RenameDoctrineRequest):
    kb = get_kb()
    updated_at = datetime.now(timezone.utc).isoformat()
    ok = kb.doctrine.rename(entry_id, body.name.strip(), updated_at)
    if not ok:
        raise HTTPException(status_code=404, detail="Doctrine entry not found")
    return {"entry_id": entry_id, "name": body.name.strip(), "updated_at": updated_at}


@router.get("/patterns")
def list_patterns():
    settings = get_active_settings_or_bootstrap()
    kb = get_kb()
    patterns = kb.attack_patterns.list_by_settings(settings.settings_id)
    return {"patterns": [p.to_dict() for p in patterns], "total": len(patterns)}


@router.get("/patterns/{pattern_id}/matches")
def pattern_matches(pattern_id: str, top_k: int = 10):
    kb = get_kb()
    matches = kb.match_results.list_by_pattern(pattern_id, top_k=top_k)
    return {
        "matches": [
            {
                "match_id": m.match_id,
                "attack_plan_id": m.attack_plan_id,
                "defense_playbook_id": m.defense_playbook_id,
                "outcome": m.outcome.value,
                "fitness_score": m.fitness_score,
                "ai_analysis_text": m.ai_analysis_text[:500] if m.ai_analysis_text else "",
                "created_at": m.created_at,
            }
            for m in matches
        ],
    }


@router.get("/bundle")
def bundle(matches_limit: int = 50):
    """
    Single-call endpoint for the Knowledge Base UI: counts + doctrine + patterns +
    playbooks + recent matches in one round-trip. Replaces 5 separate requests.
    """
    settings = get_active_settings_or_bootstrap()
    kb = get_kb()
    sid = settings.settings_id

    doctrine = kb.doctrine.list_active(sid)
    patterns = kb.attack_patterns.list_by_settings(sid)
    playbooks = kb.defense_playbooks.list_by_settings(sid)
    matches = kb.match_results.list_summary_by_settings(sid, limit=matches_limit)

    return {
        "settings_id": sid,
        "settings_name": settings.name,
        "counts": _counts(kb, sid),
        "doctrine": [e.to_dict() for e in doctrine],
        "patterns": [p.to_dict() for p in patterns],
        "playbooks": [p.to_dict() for p in playbooks],
        "matches": matches,
    }
