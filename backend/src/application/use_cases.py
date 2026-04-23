"""
Application use cases. Orchestrate domain + infrastructure via ports.
All business logic lives here; routes are thin.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.domain.entities.aircraft import Side
from src.domain.ports.knowledge_base import KnowledgeBasePort
from src.domain.ports.llm_agent import LLMAgentPort
from src.domain.services.pattern_extractor import extract_pattern
from src.domain.services.simulation_engine import run_simulation
from src.domain.value_objects.attack_plan import AttackPlan, AttackPlanSource
from src.domain.value_objects.defense_playbook import (
    Constraints,
    DefensePlaybook,
    PlaybookSource,
    StandingOrder,
    Trigger,
)
from src.domain.value_objects.doctrine_entry import DoctrineEntry
from src.domain.value_objects.match_result import AITakeaway, MatchResult
from src.domain.value_objects.settings import Settings

from src.infrastructure.ai.generators import (
    AttackPlanGenerator,
    DefensePlaybookGenerator,
    DoctrineSynthesizer,
    MatchAnalyzer,
)
from src.infrastructure.ai.live_commander import LiveCommander
from src.infrastructure.ai.random_attack_generator import generate_random_plan


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# =======================================================================
# Settings use cases
# =======================================================================

class SettingsUseCase:
    def __init__(self, kb: KnowledgeBasePort) -> None:
        self._kb = kb

    def create_from_scenario_json(
        self,
        name: str,
        scenario_path: str = "scenario/boreal_passage.json",
        notes: str = "",
    ) -> Settings:
        """Load scenario JSON from disk and create Settings row."""
        scenario = json.loads(Path(scenario_path).read_text(encoding="utf-8"))
        defender_resources = scenario.get("default_defender_resources", {})
        attacker_resources = scenario.get("default_attacker_resources", {})
        engagement_params = scenario.get("default_engagement_params", {})
        tick_minutes = scenario.get("default_tick_minutes", 5.0)
        max_ticks = scenario.get("default_max_ticks", 1000)

        settings_id = Settings.compute_id(
            scenario, defender_resources, attacker_resources,
            engagement_params, tick_minutes, max_ticks,
        )
        existing = self._kb.settings.get(settings_id)
        if existing:
            return existing

        settings = Settings(
            settings_id=settings_id,
            name=name,
            scenario=scenario,
            defender_resources=defender_resources,
            attacker_resources=attacker_resources,
            engagement_params=engagement_params,
            tick_minutes=tick_minutes,
            max_ticks=max_ticks,
            created_at=_now(),
            notes=notes,
        )
        self._kb.settings.save(settings)
        return settings

    def create(
        self,
        name: str,
        scenario: dict,
        defender_resources: dict,
        attacker_resources: dict,
        engagement_params: dict,
        tick_minutes: float = 5.0,
        max_ticks: int = 1000,
        notes: str = "",
    ) -> Settings:
        settings_id = Settings.compute_id(
            scenario, defender_resources, attacker_resources,
            engagement_params, tick_minutes, max_ticks,
        )
        existing = self._kb.settings.get(settings_id)
        if existing:
            return existing
        settings = Settings(
            settings_id=settings_id,
            name=name,
            scenario=scenario,
            defender_resources=defender_resources,
            attacker_resources=attacker_resources,
            engagement_params=engagement_params,
            tick_minutes=tick_minutes,
            max_ticks=max_ticks,
            created_at=_now(),
            notes=notes,
        )
        self._kb.settings.save(settings)
        return settings

    def list_all(self) -> list[Settings]:
        return self._kb.settings.list_all()

    def get_active(self) -> Settings | None:
        return self._kb.settings.get_active()

    def set_active(self, settings_id: str) -> None:
        self._kb.settings.set_active(settings_id)

    def delete(self, settings_id: str) -> bool:
        return self._kb.settings.delete(settings_id)


# =======================================================================
# Attack plan use cases
# =======================================================================

class AttackPlanUseCase:
    def __init__(
        self,
        kb: KnowledgeBasePort,
        attack_generator: AttackPlanGenerator,
    ) -> None:
        self._kb = kb
        self._gen = attack_generator

    def _attach_pattern(self, plan: AttackPlan) -> AttackPlan:
        pattern = extract_pattern(plan)
        plan.pattern_id = pattern.pattern_id
        existing = self._kb.attack_patterns.get(pattern.pattern_id)
        if existing:
            existing.total_plans_count = (existing.total_plans_count or 0) + 1
            self._kb.attack_patterns.upsert(existing)
        else:
            pattern.total_plans_count = 1
            self._kb.attack_patterns.upsert(pattern)
        return plan

    def generate_random(self, settings: Settings, count: int = 1, base_seed: int = 1) -> list[AttackPlan]:
        # All plans in one call share a batch tag so the UI can group them
        batch_tag = f"batch:rnd-seed{base_seed}-n{count}-t{int(datetime.now(timezone.utc).timestamp())}"
        out: list[AttackPlan] = []
        for i in range(count):
            plan = generate_random_plan(settings, seed=base_seed + i)
            plan.tags = list(plan.tags or []) + [batch_tag]
            plan = self._attach_pattern(plan)
            self._kb.attack_plans.save(plan)
            out.append(plan)
        return out

    async def generate_ai(self, settings: Settings, user_prompt: str) -> AttackPlan:
        plan = await self._gen.generate(settings, user_prompt)
        # Tag with a short prompt-derived group identifier
        short = "-".join(user_prompt.strip().lower().split()[:5])[:30] or "ai"
        plan.tags = list(plan.tags or []) + [f"batch:ai-{short}-t{int(datetime.now(timezone.utc).timestamp())}"]
        plan = self._attach_pattern(plan)
        self._kb.attack_plans.save(plan)
        return plan

    def save_custom(self, plan: AttackPlan) -> AttackPlan:
        plan = self._attach_pattern(plan)
        self._kb.attack_plans.save(plan)
        return plan

    def list_for_settings(self, settings_id: str) -> list[AttackPlan]:
        return self._kb.attack_plans.list_by_settings(settings_id)

    def get(self, plan_id: str) -> AttackPlan | None:
        return self._kb.attack_plans.get(plan_id)

    def delete(self, plan_id: str) -> bool:
        return self._kb.attack_plans.delete(plan_id)


# =======================================================================
# Defense playbook use cases
# =======================================================================

class DefensePlaybookUseCase:
    def __init__(
        self, kb: KnowledgeBasePort, playbook_generator: DefensePlaybookGenerator,
    ) -> None:
        self._kb = kb
        self._gen = playbook_generator

    async def generate_ai(
        self, settings: Settings, extra_prompt: str = "",
        similar_to_pattern_id: str | None = None,
    ) -> DefensePlaybook:
        doctrine = self._kb.doctrine.list_active(settings.settings_id)
        cases: list[MatchResult] = []
        if similar_to_pattern_id:
            cases = self._kb.match_results.list_by_pattern(similar_to_pattern_id, top_k=5)
        playbook = await self._gen.generate(settings, doctrine, cases, extra_prompt)
        self._kb.defense_playbooks.save(playbook)
        return playbook

    def create_baseline(self, settings: Settings) -> DefensePlaybook:
        """Create a simple hand-coded baseline playbook for initial training."""
        capital = None
        for c in settings.scenario.get("cities", {}).get("north", []):
            if c.get("is_capital"):
                capital = c["id"]
                break
        standing_orders = []
        if capital:
            standing_orders.append(StandingOrder(
                name="cap_over_capital",
                type="patrol",
                aircraft_type="combat_plane",
                count=2,
                zone={"type": "circle", "center": capital, "radius_km": 100},
                rotation_fuel_threshold=0.35,
                priority=10,
            ))

        # Defensive triggers cover ALL friendly asset types. Previously the
        # bomber intercept filtered to capital+city only — bombers heading for
        # airbases were ignored.
        triggers = [
            Trigger(
                name="intercept_bomber",
                when={
                    "condition": "enemy_aircraft_detected",
                    "filter": {
                        "type": "bomber",
                        "within_km_of_asset": 400,
                        "asset_types": ["capital", "major_city", "air_base", "forward_base"],
                    },
                },
                action={
                    "type": "scramble_intercept",
                    "count": 3,
                    "aircraft_type": "combat_plane",
                    "prioritize_types": ["bomber"],
                },
                priority=25,
                cooldown_ticks=5,
            ),
            Trigger(
                name="intercept_uav",
                when={
                    "condition": "enemy_aircraft_detected",
                    "filter": {
                        "type": "uav",
                        "within_km_of_asset": 350,
                        "asset_types": ["capital", "major_city", "air_base", "forward_base"],
                    },
                },
                action={
                    "type": "scramble_intercept",
                    "count": 2,
                    "aircraft_type": "combat_plane",
                    "prioritize_types": ["uav"],
                },
                priority=18,
                cooldown_ticks=5,
            ),
            Trigger(
                name="intercept_drone_swarm",
                when={
                    "condition": "enemy_aircraft_detected",
                    "filter": {
                        "type": "drone_swarm",
                        "within_km_of_asset": 300,
                        "asset_types": ["capital", "major_city", "air_base", "forward_base"],
                    },
                },
                action={
                    "type": "scramble_intercept",
                    "count": 2,
                    "aircraft_type": "combat_plane",
                    "prioritize_types": ["drone_swarm"],
                },
                priority=15,
                cooldown_ticks=5,
            ),
            Trigger(
                name="intercept_enemy_fighter",
                when={
                    "condition": "enemy_aircraft_detected",
                    "filter": {
                        "type": "combat_plane",
                        "within_km_of_asset": 300,
                        "asset_types": ["capital", "major_city", "air_base", "forward_base"],
                    },
                },
                action={
                    "type": "scramble_intercept",
                    "count": 2,
                    "aircraft_type": "combat_plane",
                    "prioritize_types": ["combat_plane"],
                },
                priority=20,
                cooldown_ticks=5,
            ),
            Trigger(
                name="commit_on_capital_threat",
                when={
                    "condition": "enemy_aircraft_detected",
                    "filter": {
                        "within_km_of_asset": 200,
                        "asset_types": ["capital"],
                    },
                },
                action={"type": "commit_reserve", "fraction": 0.5},
                priority=30,
                cooldown_ticks=15,
            ),
        ]

        playbook = DefensePlaybook(
            playbook_id=f"pbk-{uuid.uuid4().hex[:8]}",
            settings_id=settings.settings_id,
            name="Baseline Defense",
            description="Hand-coded baseline: CAP over capital, intercept bombers + drones at range.",
            source=PlaybookSource.CUSTOM,
            standing_orders=standing_orders,
            triggers=triggers,
            constraints=Constraints(),
            doctrine_notes="Prioritize capital. Keep reserves. Engage bombers early.",
            created_at=_now(),
        )
        self._kb.defense_playbooks.save(playbook)
        return playbook

    def list_for_settings(self, settings_id: str) -> list[DefensePlaybook]:
        return self._kb.defense_playbooks.list_by_settings(settings_id)

    def get(self, playbook_id: str) -> DefensePlaybook | None:
        return self._kb.defense_playbooks.get(playbook_id)

    def delete(self, playbook_id: str) -> bool:
        return self._kb.defense_playbooks.delete(playbook_id)

    def rename(self, playbook_id: str, name: str) -> bool:
        return self._kb.defense_playbooks.rename(playbook_id, name)


# =======================================================================
# Run Match (simulate + store + optional AI analysis)
# =======================================================================

class RunMatchUseCase:
    def __init__(self, kb: KnowledgeBasePort, analyzer: MatchAnalyzer | None = None) -> None:
        self._kb = kb
        self._analyzer = analyzer

    def run(
        self,
        settings: Settings,
        attack_plan: AttackPlan,
        defense_playbook: DefensePlaybook,
        analyze: bool = False,
    ) -> MatchResult:
        match = run_simulation(
            settings=settings,
            attack_plan=attack_plan,
            defense_playbook=defense_playbook,
        )
        self._kb.match_results.upsert(match)
        self._kb.attack_patterns.update_champion(
            match.pattern_id,
            match.match_id,
            match.defense_playbook_id,
            match.fitness_score,
        )
        if analyze and self._analyzer is not None:
            asyncio.create_task(self._analyze_async(
                match.match_id, attack_plan.name, defense_playbook.name,
            ))
        return match

    async def run_and_analyze(
        self,
        settings: Settings,
        attack_plan: AttackPlan,
        defense_playbook: DefensePlaybook,
    ) -> MatchResult:
        match = run_simulation(
            settings=settings,
            attack_plan=attack_plan,
            defense_playbook=defense_playbook,
        )
        if self._analyzer is not None:
            try:
                analysis, takeaways = await self._analyzer.analyze(
                    match, attack_plan.name, defense_playbook.name,
                )
                match.ai_analysis_text = analysis
                match.ai_takeaways = takeaways
                match.analysis_completed_at = _now()
            except Exception as e:
                match.ai_analysis_text = f"[Analysis failed: {e}]"
        self._kb.match_results.upsert(match)
        self._kb.attack_patterns.update_champion(
            match.pattern_id,
            match.match_id,
            match.defense_playbook_id,
            match.fitness_score,
        )
        return match

    async def _analyze_async(
        self, match_id: str, attack_name: str, playbook_name: str,
    ) -> None:
        """Background analyzer that re-saves the match with AI analysis."""
        if self._analyzer is None:
            return
        match = self._kb.match_results.get(match_id)
        if not match:
            return
        try:
            analysis, takeaways = await self._analyzer.analyze(
                match, attack_name, playbook_name,
            )
            match.ai_analysis_text = analysis
            match.ai_takeaways = takeaways
            match.analysis_completed_at = _now()
            self._kb.match_results.upsert(match)
        except Exception:
            pass
