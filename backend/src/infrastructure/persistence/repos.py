"""All knowledge-base repo implementations."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.domain.ports.knowledge_base import (
    AttackPatternRepositoryPort,
    AttackPlanRepositoryPort,
    DefensePlaybookRepositoryPort,
    DoctrineRepositoryPort,
    KnowledgeBasePort,
    MatchResultRepositoryPort,
    SettingsRepositoryPort,
)
from src.domain.value_objects.attack_pattern import AttackPattern
from src.domain.value_objects.attack_plan import AttackPlan, AttackPlanSource
from src.domain.value_objects.defense_playbook import DefensePlaybook, PlaybookSource
from src.domain.value_objects.doctrine_entry import DoctrineEntry
from src.domain.value_objects.match_result import (
    AITakeaway,
    MatchResult,
    SimulationOutcome,
)
from src.domain.value_objects.metrics import SimulationMetrics
from src.domain.value_objects.settings import Settings

from .database import get_session
from .models import (
    AttackPatternModel,
    AttackPlanModel,
    DefensePlaybookModel,
    DoctrineEntryModel,
    MatchResultModel,
    SettingsModel,
)


# =======================================================================
# Settings
# =======================================================================

class SqlSettingsRepo(SettingsRepositoryPort):
    def save(self, settings: Settings) -> str:
        session = get_session()
        try:
            existing = session.query(SettingsModel).get(settings.settings_id)
            if existing:
                existing.name = settings.name
                existing.last_used_at = datetime.now(timezone.utc).isoformat()
                existing.notes = settings.notes
            else:
                session.add(SettingsModel(
                    settings_id=settings.settings_id,
                    name=settings.name,
                    scenario_json=json.dumps(settings.scenario),
                    defender_resources_json=json.dumps(settings.defender_resources),
                    attacker_resources_json=json.dumps(settings.attacker_resources),
                    engagement_params_json=json.dumps(settings.engagement_params),
                    tick_minutes=settings.tick_minutes,
                    max_ticks=settings.max_ticks,
                    is_active=False,
                    created_at=settings.created_at,
                    last_used_at=settings.created_at,
                    notes=settings.notes,
                ))
            session.commit()
            return settings.settings_id
        finally:
            session.close()

    def get(self, settings_id: str) -> Settings | None:
        session = get_session()
        try:
            m = session.query(SettingsModel).get(settings_id)
            return self._to_domain(m) if m else None
        finally:
            session.close()

    def list_all(self) -> list[Settings]:
        session = get_session()
        try:
            return [self._to_domain(m) for m in session.query(SettingsModel).all()]
        finally:
            session.close()

    def get_active(self) -> Settings | None:
        session = get_session()
        try:
            m = session.query(SettingsModel).filter_by(is_active=True).first()
            return self._to_domain(m) if m else None
        finally:
            session.close()

    def set_active(self, settings_id: str) -> None:
        session = get_session()
        try:
            session.query(SettingsModel).update({SettingsModel.is_active: False})
            m = session.query(SettingsModel).get(settings_id)
            if m:
                m.is_active = True
                m.last_used_at = datetime.now(timezone.utc).isoformat()
            session.commit()
        finally:
            session.close()

    def delete(self, settings_id: str) -> bool:
        session = get_session()
        try:
            m = session.query(SettingsModel).get(settings_id)
            if not m:
                return False
            session.delete(m)
            session.commit()
            return True
        finally:
            session.close()

    @staticmethod
    def _to_domain(m: SettingsModel) -> Settings:
        return Settings(
            settings_id=m.settings_id,
            name=m.name,
            scenario=json.loads(m.scenario_json),
            defender_resources=json.loads(m.defender_resources_json),
            attacker_resources=json.loads(m.attacker_resources_json),
            engagement_params=json.loads(m.engagement_params_json),
            tick_minutes=m.tick_minutes,
            max_ticks=m.max_ticks,
            created_at=m.created_at,
            notes=m.notes or "",
        )


# =======================================================================
# Attack Plans
# =======================================================================

class SqlAttackPlanRepo(AttackPlanRepositoryPort):
    def save(self, plan: AttackPlan) -> str:
        session = get_session()
        try:
            existing = session.query(AttackPlanModel).get(plan.plan_id)
            actions_json = json.dumps([a for a in plan.to_dict()["actions"]])
            if existing:
                existing.name = plan.name
                existing.pattern_id = plan.pattern_id
                existing.description = plan.description
                existing.actions_json = actions_json
                existing.tags_json = json.dumps(plan.tags)
            else:
                session.add(AttackPlanModel(
                    plan_id=plan.plan_id,
                    settings_id=plan.settings_id,
                    pattern_id=plan.pattern_id,
                    name=plan.name,
                    description=plan.description,
                    source=plan.source.value,
                    actions_json=actions_json,
                    tags_json=json.dumps(plan.tags),
                    created_at=plan.created_at,
                ))
            session.commit()
            return plan.plan_id
        finally:
            session.close()

    def get(self, plan_id: str) -> AttackPlan | None:
        session = get_session()
        try:
            m = session.query(AttackPlanModel).get(plan_id)
            return self._to_domain(m) if m else None
        finally:
            session.close()

    def list_by_settings(self, settings_id: str) -> list[AttackPlan]:
        session = get_session()
        try:
            return [self._to_domain(m) for m in
                    session.query(AttackPlanModel).filter_by(settings_id=settings_id).all()]
        finally:
            session.close()

    def list_by_pattern(self, pattern_id: str) -> list[AttackPlan]:
        session = get_session()
        try:
            return [self._to_domain(m) for m in
                    session.query(AttackPlanModel).filter_by(pattern_id=pattern_id).all()]
        finally:
            session.close()

    def count_by_settings(self, settings_id: str) -> int:
        session = get_session()
        try:
            return session.query(AttackPlanModel).filter_by(settings_id=settings_id).count()
        finally:
            session.close()

    def delete(self, plan_id: str) -> bool:
        session = get_session()
        try:
            m = session.query(AttackPlanModel).get(plan_id)
            if not m:
                return False
            session.delete(m)
            session.commit()
            return True
        finally:
            session.close()

    @staticmethod
    def _to_domain(m: AttackPlanModel) -> AttackPlan:
        return AttackPlan.from_dict({
            "plan_id": m.plan_id,
            "settings_id": m.settings_id,
            "pattern_id": m.pattern_id,
            "name": m.name,
            "description": m.description,
            "source": m.source,
            "actions": json.loads(m.actions_json),
            "tags": json.loads(m.tags_json or "[]"),
            "created_at": m.created_at,
        })


# =======================================================================
# Attack Patterns
# =======================================================================

class SqlAttackPatternRepo(AttackPatternRepositoryPort):
    def upsert(self, pattern: AttackPattern) -> str:
        session = get_session()
        try:
            existing = session.query(AttackPatternModel).get(pattern.pattern_id)
            if existing:
                existing.total_plans_count = pattern.total_plans_count
                existing.total_matches_count = pattern.total_matches_count
                if pattern.best_match_id:
                    existing.best_match_id = pattern.best_match_id
                    existing.best_defense_playbook_id = pattern.best_defense_playbook_id
                    existing.best_fitness_score = pattern.best_fitness_score
            else:
                session.add(AttackPatternModel(
                    pattern_id=pattern.pattern_id,
                    settings_id=pattern.settings_id,
                    canonical_description=pattern.canonical_description,
                    feature_tags_json=json.dumps(pattern.feature_tags),
                    force_composition_json=json.dumps(pattern.force_composition),
                    target_profile=pattern.target_profile,
                    wave_count=pattern.wave_count,
                    first_seen_at=pattern.first_seen_at,
                    total_plans_count=pattern.total_plans_count,
                    total_matches_count=pattern.total_matches_count,
                    best_defense_playbook_id=pattern.best_defense_playbook_id,
                    best_fitness_score=pattern.best_fitness_score,
                    best_match_id=pattern.best_match_id,
                ))
            session.commit()
            return pattern.pattern_id
        finally:
            session.close()

    def get(self, pattern_id: str) -> AttackPattern | None:
        session = get_session()
        try:
            m = session.query(AttackPatternModel).get(pattern_id)
            return self._to_domain(m) if m else None
        finally:
            session.close()

    def list_by_settings(self, settings_id: str) -> list[AttackPattern]:
        session = get_session()
        try:
            return [self._to_domain(m) for m in
                    session.query(AttackPatternModel).filter_by(settings_id=settings_id).all()]
        finally:
            session.close()

    def count_by_settings(self, settings_id: str) -> int:
        session = get_session()
        try:
            return session.query(AttackPatternModel).filter_by(settings_id=settings_id).count()
        finally:
            session.close()

    def update_champion(
        self, pattern_id: str, match_id: str, playbook_id: str, fitness: float,
    ) -> None:
        session = get_session()
        try:
            m = session.query(AttackPatternModel).get(pattern_id)
            if m:
                if m.best_fitness_score is None or fitness > m.best_fitness_score:
                    m.best_fitness_score = fitness
                    m.best_match_id = match_id
                    m.best_defense_playbook_id = playbook_id
                m.total_matches_count = (m.total_matches_count or 0) + 1
                session.commit()
        finally:
            session.close()

    @staticmethod
    def _to_domain(m: AttackPatternModel) -> AttackPattern:
        return AttackPattern(
            pattern_id=m.pattern_id,
            settings_id=m.settings_id,
            canonical_description=m.canonical_description,
            feature_tags=json.loads(m.feature_tags_json),
            force_composition=json.loads(m.force_composition_json),
            target_profile=m.target_profile,
            wave_count=m.wave_count,
            first_seen_at=m.first_seen_at,
            total_plans_count=m.total_plans_count or 0,
            total_matches_count=m.total_matches_count or 0,
            best_defense_playbook_id=m.best_defense_playbook_id,
            best_fitness_score=m.best_fitness_score,
            best_match_id=m.best_match_id,
        )


# =======================================================================
# Defense Playbooks
# =======================================================================

class SqlDefensePlaybookRepo(DefensePlaybookRepositoryPort):
    def save(self, playbook: DefensePlaybook) -> str:
        session = get_session()
        try:
            d = playbook.to_dict()
            existing = session.query(DefensePlaybookModel).get(playbook.playbook_id)
            if existing:
                existing.name = playbook.name
                existing.description = playbook.description
                existing.standing_orders_json = json.dumps(d["standing_orders"])
                existing.triggers_json = json.dumps(d["triggers"])
                existing.constraints_json = json.dumps(d["constraints"])
                existing.doctrine_notes = playbook.doctrine_notes
            else:
                session.add(DefensePlaybookModel(
                    playbook_id=playbook.playbook_id,
                    settings_id=playbook.settings_id,
                    name=playbook.name,
                    description=playbook.description,
                    source=playbook.source.value,
                    standing_orders_json=json.dumps(d["standing_orders"]),
                    triggers_json=json.dumps(d["triggers"]),
                    constraints_json=json.dumps(d["constraints"]),
                    doctrine_notes=playbook.doctrine_notes,
                    parent_playbook_id=playbook.parent_playbook_id,
                    created_at=playbook.created_at,
                ))
            session.commit()
            return playbook.playbook_id
        finally:
            session.close()

    def get(self, playbook_id: str) -> DefensePlaybook | None:
        session = get_session()
        try:
            m = session.query(DefensePlaybookModel).get(playbook_id)
            return self._to_domain(m) if m else None
        finally:
            session.close()

    def list_by_settings(self, settings_id: str) -> list[DefensePlaybook]:
        session = get_session()
        try:
            return [self._to_domain(m) for m in
                    session.query(DefensePlaybookModel).filter_by(settings_id=settings_id).all()]
        finally:
            session.close()

    def count_by_settings(self, settings_id: str) -> int:
        session = get_session()
        try:
            return session.query(DefensePlaybookModel).filter_by(settings_id=settings_id).count()
        finally:
            session.close()

    def delete(self, playbook_id: str) -> bool:
        session = get_session()
        try:
            m = session.query(DefensePlaybookModel).get(playbook_id)
            if not m:
                return False
            session.delete(m)
            session.commit()
            return True
        finally:
            session.close()

    def rename(self, playbook_id: str, name: str) -> bool:
        session = get_session()
        try:
            m = session.query(DefensePlaybookModel).get(playbook_id)
            if not m:
                return False
            m.name = name
            session.commit()
            return True
        finally:
            session.close()

    @staticmethod
    def _to_domain(m: DefensePlaybookModel) -> DefensePlaybook:
        return DefensePlaybook.from_dict({
            "playbook_id": m.playbook_id,
            "settings_id": m.settings_id,
            "name": m.name,
            "description": m.description,
            "source": m.source,
            "standing_orders": json.loads(m.standing_orders_json),
            "triggers": json.loads(m.triggers_json),
            "constraints": json.loads(m.constraints_json),
            "doctrine_notes": m.doctrine_notes or "",
            "parent_playbook_id": m.parent_playbook_id,
            "created_at": m.created_at,
        })


# =======================================================================
# Match Results
# =======================================================================

class SqlMatchResultRepo(MatchResultRepositoryPort):
    def upsert(self, match: MatchResult) -> str:
        session = get_session()
        try:
            existing = session.query(MatchResultModel).get(match.match_id)
            if existing:
                session.delete(existing)
                session.flush()
            session.add(MatchResultModel(
                match_id=match.match_id,
                settings_id=match.settings_id,
                attack_plan_id=match.attack_plan_id,
                pattern_id=match.pattern_id,
                defense_playbook_id=match.defense_playbook_id,
                outcome=match.outcome.value,
                fitness_score=match.fitness_score,
                metrics_json=json.dumps(match.metrics.to_dict()),
                event_log_json=json.dumps(match.event_log),
                ai_analysis_text=match.ai_analysis_text,
                ai_takeaways_json=json.dumps([t.to_dict() for t in match.ai_takeaways]),
                created_at=match.created_at,
                analysis_completed_at=match.analysis_completed_at,
            ))
            session.commit()
            return match.match_id
        finally:
            session.close()

    def get(self, match_id: str) -> MatchResult | None:
        session = get_session()
        try:
            m = session.query(MatchResultModel).get(match_id)
            return self._to_domain(m) if m else None
        finally:
            session.close()

    def list_by_pattern(self, pattern_id: str, top_k: int = 5) -> list[MatchResult]:
        session = get_session()
        try:
            rows = (
                session.query(MatchResultModel)
                .filter_by(pattern_id=pattern_id)
                .order_by(MatchResultModel.fitness_score.desc())
                .limit(top_k)
                .all()
            )
            return [self._to_domain(m) for m in rows]
        finally:
            session.close()

    def list_by_attack_plan(self, attack_plan_id: str) -> list[MatchResult]:
        session = get_session()
        try:
            return [self._to_domain(m) for m in
                    session.query(MatchResultModel).filter_by(attack_plan_id=attack_plan_id).all()]
        finally:
            session.close()

    def list_by_playbook(self, playbook_id: str) -> list[MatchResult]:
        session = get_session()
        try:
            return [self._to_domain(m) for m in
                    session.query(MatchResultModel).filter_by(defense_playbook_id=playbook_id).all()]
        finally:
            session.close()

    def list_by_settings(self, settings_id: str, limit: int = 100) -> list[MatchResult]:
        session = get_session()
        try:
            rows = (
                session.query(MatchResultModel)
                .filter_by(settings_id=settings_id)
                .order_by(MatchResultModel.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._to_domain(m) for m in rows]
        finally:
            session.close()

    def count_by_settings(self, settings_id: str) -> int:
        """Cheap COUNT(*) query — avoids loading match rows for summary views."""
        session = get_session()
        try:
            return (
                session.query(MatchResultModel)
                .filter_by(settings_id=settings_id)
                .count()
            )
        finally:
            session.close()

    def list_summary_by_settings(
        self, settings_id: str, limit: int = 100,
    ) -> list[dict]:
        """
        Lightweight list view — does NOT load event_log_json.
        Returns pre-computed dicts ready for API response. Use this for
        listing/dashboard views where replay data isn't needed.

        Event log is the heaviest column (often megabytes); skipping it
        makes the list query 10-50x faster for large result sets.
        """
        session = get_session()
        try:
            rows = (
                session.query(
                    MatchResultModel.match_id,
                    MatchResultModel.settings_id,
                    MatchResultModel.attack_plan_id,
                    MatchResultModel.pattern_id,
                    MatchResultModel.defense_playbook_id,
                    MatchResultModel.outcome,
                    MatchResultModel.fitness_score,
                    MatchResultModel.metrics_json,
                    MatchResultModel.created_at,
                    MatchResultModel.analysis_completed_at,
                )
                .filter(MatchResultModel.settings_id == settings_id)
                .order_by(MatchResultModel.created_at.desc())
                .limit(limit)
                .all()
            )
            out: list[dict] = []
            for r in rows:
                metrics = json.loads(r.metrics_json) if r.metrics_json else {}
                out.append({
                    "match_id": r.match_id,
                    "settings_id": r.settings_id,
                    "attack_plan_id": r.attack_plan_id,
                    "pattern_id": r.pattern_id,
                    "defense_playbook_id": r.defense_playbook_id,
                    "outcome": r.outcome,
                    "fitness_score": r.fitness_score,
                    "total_civilian_casualties": metrics.get("total_civilian_casualties", 0),
                    "capital_survived": metrics.get("capital_survived", True),
                    "aircraft_lost": metrics.get("aircraft_lost", 0),
                    "aircraft_remaining": metrics.get("aircraft_remaining", 0),
                    "engagement_win_rate": metrics.get("engagement_win_rate", 0.0),
                    "enemy_sorties_deterred": metrics.get("enemy_sorties_deterred", 0),
                    "created_at": r.created_at,
                    "has_ai_analysis": r.analysis_completed_at is not None,
                })
            return out
        finally:
            session.close()

    @staticmethod
    def _to_domain(m: MatchResultModel) -> MatchResult:
        return MatchResult(
            match_id=m.match_id,
            settings_id=m.settings_id,
            attack_plan_id=m.attack_plan_id,
            pattern_id=m.pattern_id,
            defense_playbook_id=m.defense_playbook_id,
            outcome=SimulationOutcome(m.outcome),
            fitness_score=m.fitness_score,
            metrics=SimulationMetrics(**json.loads(m.metrics_json)),
            event_log=json.loads(m.event_log_json),
            ai_analysis_text=m.ai_analysis_text or "",
            ai_takeaways=[AITakeaway.from_dict(t) for t in json.loads(m.ai_takeaways_json or "[]")],
            created_at=m.created_at,
            analysis_completed_at=m.analysis_completed_at,
        )


# =======================================================================
# Doctrine
# =======================================================================

class SqlDoctrineRepo(DoctrineRepositoryPort):
    def save(self, entry: DoctrineEntry) -> str:
        session = get_session()
        try:
            existing = session.query(DoctrineEntryModel).get(entry.entry_id)
            if existing:
                existing.name = entry.name
                existing.principle_text = entry.principle_text
                existing.confidence_score = entry.confidence_score
                existing.is_active = entry.is_active
                existing.human_edited = entry.human_edited
                existing.supporting_match_ids_json = json.dumps(entry.supporting_match_ids)
                existing.updated_at = entry.updated_at
            else:
                session.add(DoctrineEntryModel(
                    entry_id=entry.entry_id,
                    settings_id=entry.settings_id,
                    category=entry.category,
                    name=entry.name,
                    principle_text=entry.principle_text,
                    trigger_conditions_json=json.dumps(entry.trigger_conditions),
                    supporting_match_ids_json=json.dumps(entry.supporting_match_ids),
                    confidence_score=entry.confidence_score,
                    version=entry.version,
                    parent_entry_id=entry.parent_entry_id,
                    is_active=entry.is_active,
                    human_edited=entry.human_edited,
                    created_at=entry.created_at,
                    updated_at=entry.updated_at,
                ))
            session.commit()
            return entry.entry_id
        finally:
            session.close()

    def get(self, entry_id: str) -> DoctrineEntry | None:
        session = get_session()
        try:
            m = session.query(DoctrineEntryModel).get(entry_id)
            return self._to_domain(m) if m else None
        finally:
            session.close()

    def list_active(
        self, settings_id: str, category: str | None = None,
    ) -> list[DoctrineEntry]:
        session = get_session()
        try:
            q = session.query(DoctrineEntryModel).filter_by(settings_id=settings_id, is_active=True)
            if category:
                q = q.filter_by(category=category)
            return [self._to_domain(m) for m in q.all()]
        finally:
            session.close()

    def list_versions(self, settings_id: str, category: str) -> list[DoctrineEntry]:
        session = get_session()
        try:
            return [self._to_domain(m) for m in
                    session.query(DoctrineEntryModel)
                    .filter_by(settings_id=settings_id, category=category)
                    .order_by(DoctrineEntryModel.version.desc())
                    .all()]
        finally:
            session.close()

    def count_active_by_settings(self, settings_id: str) -> int:
        session = get_session()
        try:
            return (
                session.query(DoctrineEntryModel)
                .filter_by(settings_id=settings_id, is_active=True)
                .count()
            )
        finally:
            session.close()

    def rename(self, entry_id: str, name: str, updated_at: str) -> bool:
        session = get_session()
        try:
            m = session.query(DoctrineEntryModel).get(entry_id)
            if not m:
                return False
            m.name = name
            m.human_edited = True
            m.updated_at = updated_at
            session.commit()
            return True
        finally:
            session.close()

    def supersede(self, old_entry_id: str, new_entry: DoctrineEntry) -> str:
        session = get_session()
        try:
            old = session.query(DoctrineEntryModel).get(old_entry_id)
            if old:
                old.is_active = False
                new_entry.parent_entry_id = old_entry_id
                new_entry.version = (old.version or 1) + 1
            self.save(new_entry)
            session.commit()
            return new_entry.entry_id
        finally:
            session.close()

    @staticmethod
    def _to_domain(m: DoctrineEntryModel) -> DoctrineEntry:
        return DoctrineEntry(
            entry_id=m.entry_id,
            settings_id=m.settings_id,
            category=m.category,
            name=getattr(m, "name", "") or "",
            principle_text=m.principle_text,
            trigger_conditions=json.loads(m.trigger_conditions_json or "{}"),
            supporting_match_ids=json.loads(m.supporting_match_ids_json or "[]"),
            confidence_score=m.confidence_score or 0.5,
            version=m.version or 1,
            parent_entry_id=m.parent_entry_id,
            is_active=bool(m.is_active),
            human_edited=bool(m.human_edited),
            created_at=m.created_at,
            updated_at=m.updated_at,
        )


# =======================================================================
# Aggregator
# =======================================================================

class SqlKnowledgeBase(KnowledgeBasePort):
    def __init__(self) -> None:
        self.settings = SqlSettingsRepo()
        self.attack_plans = SqlAttackPlanRepo()
        self.attack_patterns = SqlAttackPatternRepo()
        self.defense_playbooks = SqlDefensePlaybookRepo()
        self.match_results = SqlMatchResultRepo()
        self.doctrine = SqlDoctrineRepo()
