"""Pydantic schemas for API requests/responses."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


# ========== Settings ==========

class CreateSettingsFromScenarioRequest(BaseModel):
    name: str = "Boreal Passage — Standard"
    scenario_path: str = "scenario/boreal_passage.json"
    notes: str = ""


class SettingsResponse(BaseModel):
    settings_id: str
    name: str
    tick_minutes: float
    max_ticks: int
    created_at: str
    notes: str
    is_active: bool = False


# ========== Attack Plans ==========

class GenerateRandomAttackRequest(BaseModel):
    count: int = 1
    base_seed: int = 1


class GenerateAIAttackRequest(BaseModel):
    prompt: str


class AttackPlanResponse(BaseModel):
    plan_id: str
    settings_id: str
    pattern_id: str | None
    name: str
    description: str
    source: str
    tags: list[str]
    actions: list[dict]
    created_at: str


# ========== Defense Playbooks ==========

class GenerateAIPlaybookRequest(BaseModel):
    prompt: str = ""
    similar_to_pattern_id: str | None = None


class PlaybookResponse(BaseModel):
    playbook_id: str
    settings_id: str
    name: str
    description: str
    source: str
    doctrine_notes: str
    standing_orders: list[dict]
    triggers: list[dict]
    constraints: dict
    created_at: str


# ========== Match / Evaluation ==========

class RunEvaluationRequest(BaseModel):
    attack_plan_id: str
    defense_playbook_id: str
    analyze: bool = True
    live_commander: bool = False


class MatchResultResponse(BaseModel):
    match_id: str
    settings_id: str
    attack_plan_id: str
    pattern_id: str
    defense_playbook_id: str
    outcome: str
    fitness_score: float
    metrics: dict
    ai_analysis_text: str = ""
    ai_takeaways: list[dict] = Field(default_factory=list)
    created_at: str


# ========== Training ==========

class StartTrainingRequest(BaseModel):
    attack_plan_ids: list[str]
    defense_playbook_id: str | None = None       # None = generate new one
    extra_playbook_prompt: str = ""


class TrainingJobResponse(BaseModel):
    job_id: str
    settings_id: str
    status: str
    progress_current: int
    progress_total: int
    started_at: str
    completed_at: str | None = None
    result_summary: dict | None = None
    error: str | None = None


# ========== Knowledge Base ==========

class PatternResponse(BaseModel):
    pattern_id: str
    settings_id: str
    canonical_description: str
    feature_tags: list[str]
    force_composition: dict
    target_profile: str
    wave_count: int
    total_plans_count: int
    total_matches_count: int
    best_defense_playbook_id: str | None = None
    best_fitness_score: float | None = None
    best_match_id: str | None = None


class DoctrineEntryResponse(BaseModel):
    entry_id: str
    settings_id: str
    category: str
    name: str = ""
    principle_text: str
    confidence_score: float
    version: int
    is_active: bool
    human_edited: bool
    created_at: str
    updated_at: str


class RenameDoctrineRequest(BaseModel):
    name: str


class RenamePlaybookRequest(BaseModel):
    name: str
