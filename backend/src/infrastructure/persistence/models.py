from __future__ import annotations

from sqlalchemy import Column, String, Integer, Float, Text, Boolean

from .database import DBBase


class SettingsModel(DBBase):
    __tablename__ = "settings"
    settings_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    scenario_json = Column(Text, nullable=False)
    defender_resources_json = Column(Text, nullable=False)
    attacker_resources_json = Column(Text, nullable=False)
    engagement_params_json = Column(Text, nullable=False)
    tick_minutes = Column(Float, nullable=False)
    max_ticks = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(String, nullable=False)
    last_used_at = Column(String, nullable=False)
    notes = Column(Text, nullable=True)


class AttackPlanModel(DBBase):
    __tablename__ = "attack_plans"
    plan_id = Column(String, primary_key=True)
    settings_id = Column(String, nullable=False, index=True)
    pattern_id = Column(String, nullable=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    source = Column(String, nullable=False)
    actions_json = Column(Text, nullable=False)
    tags_json = Column(Text, nullable=True)
    created_at = Column(String, nullable=False)


class AttackPatternModel(DBBase):
    __tablename__ = "attack_patterns"
    pattern_id = Column(String, primary_key=True)
    settings_id = Column(String, nullable=False, index=True)
    canonical_description = Column(Text, nullable=False)
    feature_tags_json = Column(Text, nullable=False)
    force_composition_json = Column(Text, nullable=False)
    target_profile = Column(String, nullable=False)
    wave_count = Column(Integer, nullable=False)
    first_seen_at = Column(String, nullable=False)
    total_plans_count = Column(Integer, default=0)
    total_matches_count = Column(Integer, default=0)
    best_defense_playbook_id = Column(String, nullable=True)
    best_fitness_score = Column(Float, nullable=True)
    best_match_id = Column(String, nullable=True)


class DefensePlaybookModel(DBBase):
    __tablename__ = "defense_playbooks"
    playbook_id = Column(String, primary_key=True)
    settings_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    source = Column(String, nullable=False)
    standing_orders_json = Column(Text, nullable=False)
    triggers_json = Column(Text, nullable=False)
    constraints_json = Column(Text, nullable=False)
    doctrine_notes = Column(Text, nullable=True)
    parent_playbook_id = Column(String, nullable=True)
    created_at = Column(String, nullable=False)


class MatchResultModel(DBBase):
    __tablename__ = "match_results"
    match_id = Column(String, primary_key=True)
    settings_id = Column(String, nullable=False, index=True)
    attack_plan_id = Column(String, nullable=False, index=True)
    pattern_id = Column(String, nullable=False, index=True)
    defense_playbook_id = Column(String, nullable=False, index=True)
    outcome = Column(String, nullable=False)
    fitness_score = Column(Float, nullable=False, index=True)
    metrics_json = Column(Text, nullable=False)
    event_log_json = Column(Text, nullable=False)
    ai_analysis_text = Column(Text, nullable=True)
    ai_takeaways_json = Column(Text, nullable=True)
    created_at = Column(String, nullable=False)
    analysis_completed_at = Column(String, nullable=True)


class DoctrineEntryModel(DBBase):
    __tablename__ = "doctrine_entries"
    entry_id = Column(String, primary_key=True)
    settings_id = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    name = Column(String, nullable=True, default="")
    principle_text = Column(Text, nullable=False)
    trigger_conditions_json = Column(Text, nullable=True)
    supporting_match_ids_json = Column(Text, nullable=True)
    confidence_score = Column(Float, default=0.5)
    version = Column(Integer, default=1)
    parent_entry_id = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    human_edited = Column(Boolean, default=False)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)


class TrainingJobModel(DBBase):
    __tablename__ = "training_jobs"
    job_id = Column(String, primary_key=True)
    settings_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False)           # pending | running | completed | failed
    progress_current = Column(Integer, default=0)
    progress_total = Column(Integer, default=0)
    config_json = Column(Text, nullable=False)
    result_summary_json = Column(Text, nullable=True)
    started_at = Column(String, nullable=False)
    completed_at = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)


class EvaluationConversationModel(DBBase):
    __tablename__ = "evaluation_conversations"
    eval_id = Column(String, primary_key=True)
    match_id = Column(String, nullable=False, index=True)
    messages_json = Column(Text, nullable=False)
    commands_issued_json = Column(Text, nullable=True)
    total_input_tokens = Column(Integer, default=0)
    total_output_tokens = Column(Integer, default=0)
    cached_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    started_at = Column(String, nullable=False)
    ended_at = Column(String, nullable=True)
