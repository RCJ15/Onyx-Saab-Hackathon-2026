from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.infrastructure.api.dependencies import (
    get_active_settings_or_bootstrap,
    get_playbook_uc,
)
from src.infrastructure.api.schemas import GenerateAIPlaybookRequest, RenamePlaybookRequest


router = APIRouter(prefix="/defense-playbooks", tags=["defense-playbooks"])


@router.get("")
def list_playbooks():
    settings = get_active_settings_or_bootstrap()
    uc = get_playbook_uc()
    playbooks = uc.list_for_settings(settings.settings_id)
    return {"playbooks": [p.to_dict() for p in playbooks], "total": len(playbooks)}


@router.get("/{playbook_id}")
def get_playbook(playbook_id: str):
    uc = get_playbook_uc()
    p = uc.get(playbook_id)
    if not p:
        raise HTTPException(404, "Playbook not found")
    return p.to_dict()


@router.post("/generate-ai")
async def generate_ai(req: GenerateAIPlaybookRequest):
    settings = get_active_settings_or_bootstrap()
    uc = get_playbook_uc()
    try:
        p = await uc.generate_ai(
            settings,
            extra_prompt=req.prompt,
            similar_to_pattern_id=req.similar_to_pattern_id,
        )
        return p.to_dict()
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Playbook generation failed: {e}")


@router.post("/create-baseline")
def create_baseline():
    settings = get_active_settings_or_bootstrap()
    uc = get_playbook_uc()
    p = uc.create_baseline(settings)
    return p.to_dict()


@router.patch("/{playbook_id}/name")
def rename_playbook(playbook_id: str, body: RenamePlaybookRequest):
    uc = get_playbook_uc()
    if not uc.rename(playbook_id, body.name.strip()):
        raise HTTPException(404, "Playbook not found")
    return {"playbook_id": playbook_id, "name": body.name.strip()}


@router.delete("/{playbook_id}")
def delete_playbook(playbook_id: str):
    uc = get_playbook_uc()
    if not uc.delete(playbook_id):
        raise HTTPException(404, "Playbook not found")
    return {"deleted": playbook_id}
