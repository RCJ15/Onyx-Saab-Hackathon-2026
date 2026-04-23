"""
Training orchestrator. Generates (or reuses) a defense playbook, runs it
against a batch of attack plans, analyzes each match, synthesizes doctrine.

Designed to run as a background asyncio task; progress reported via callback.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.ports.knowledge_base import KnowledgeBasePort
from src.domain.services.simulation_engine import run_simulation
from src.domain.value_objects.doctrine_entry import DoctrineEntry
from src.domain.value_objects.match_result import AITakeaway, MatchResult
from src.domain.value_objects.settings import Settings

from src.infrastructure.ai.generators import (
    DefensePlaybookGenerator,
    DoctrineSynthesizer,
    MatchAnalyzer,
)
from src.infrastructure.persistence.database import get_session
from src.infrastructure.persistence.models import TrainingJobModel


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Keep strong references so background tasks aren't garbage-collected.
_ACTIVE_TASKS: set[asyncio.Task] = set()


def _run_one_sim(args: tuple) -> MatchResult:
    """Module-level worker for ProcessPoolExecutor. Must be picklable.

    Runs a single deterministic simulation. Pure — no DB, no LLM, no I/O.
    """
    settings, attack_plan, defense_playbook = args
    return run_simulation(
        settings=settings,
        attack_plan=attack_plan,
        defense_playbook=defense_playbook,
    )


@dataclass
class TrainingJobStatus:
    job_id: str
    settings_id: str
    status: str                       # "running" | "completed" | "failed"
    progress_current: int
    progress_total: int
    matches_created: list[str] = field(default_factory=list)
    playbook_id: str | None = None
    doctrine_updates: dict = field(default_factory=dict)
    error: str | None = None
    started_at: str = ""
    completed_at: str | None = None


class TrainingOrchestrator:
    def __init__(
        self,
        kb: KnowledgeBasePort,
        playbook_generator: DefensePlaybookGenerator,
        match_analyzer: MatchAnalyzer,
        doctrine_synthesizer: DoctrineSynthesizer,
    ) -> None:
        self._kb = kb
        self._pb_gen = playbook_generator
        self._analyzer = match_analyzer
        self._synth = doctrine_synthesizer

    def start_job(
        self,
        settings: Settings,
        attack_plan_ids: list[str],
        defense_playbook_id: str | None = None,
        extra_playbook_prompt: str = "",
    ) -> str:
        """Create a training job row and schedule async execution."""
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        config = {
            "settings_id": settings.settings_id,
            "attack_plan_ids": attack_plan_ids,
            "defense_playbook_id": defense_playbook_id,
            "extra_playbook_prompt": extra_playbook_prompt,
        }
        session = get_session()
        try:
            session.add(TrainingJobModel(
                job_id=job_id,
                settings_id=settings.settings_id,
                status="pending",
                progress_current=0,
                progress_total=len(attack_plan_ids),
                config_json=json.dumps(config),
                started_at=_now(),
            ))
            session.commit()
        finally:
            session.close()

        task = asyncio.create_task(self._run_job(job_id, settings, config))
        _ACTIVE_TASKS.add(task)
        task.add_done_callback(_ACTIVE_TASKS.discard)
        return job_id

    def get_job_status(self, job_id: str) -> dict | None:
        session = get_session()
        try:
            m = session.query(TrainingJobModel).get(job_id)
            if not m:
                return None
            return {
                "job_id": m.job_id,
                "settings_id": m.settings_id,
                "status": m.status,
                "progress_current": m.progress_current,
                "progress_total": m.progress_total,
                "config": json.loads(m.config_json),
                "result_summary": json.loads(m.result_summary_json) if m.result_summary_json else None,
                "started_at": m.started_at,
                "completed_at": m.completed_at,
                "error": m.error_message,
            }
        finally:
            session.close()

    def list_jobs(self, settings_id: str | None = None) -> list[dict]:
        session = get_session()
        try:
            q = session.query(TrainingJobModel)
            if settings_id:
                q = q.filter_by(settings_id=settings_id)
            rows = q.order_by(TrainingJobModel.started_at.desc()).limit(50).all()
            return [
                {
                    "job_id": m.job_id,
                    "settings_id": m.settings_id,
                    "status": m.status,
                    "progress_current": m.progress_current,
                    "progress_total": m.progress_total,
                    "started_at": m.started_at,
                    "completed_at": m.completed_at,
                }
                for m in rows
            ]
        finally:
            session.close()

    async def _run_job(
        self, job_id: str, settings: Settings, config: dict,
    ) -> None:
        """Background execution.

        Progress is reported as a weighted sum across all phases, not just
        simulations, so the bar reflects time remaining rather than hitting
        100% as soon as the CPU-bound sim phase ends.
        """
        self._update_job_status(job_id, status="running")

        # Relative time weights per unit of work. LLM calls dominate wall time;
        # simulations run in parallel on CPU cores. These are approximations
        # tuned so the bar advances at a roughly uniform rate across phases.
        W_PLAYBOOK = 5   # single LLM call (0 if reusing an existing playbook)
        W_SIM = 1        # per simulation
        W_ANALYSIS = 4   # per match analysis (LLM)
        W_PERSIST = 1    # total
        W_SYNTH = 6      # single LLM call on aggregated takeaways

        try:
            playbook_id = config.get("defense_playbook_id")
            attack_plan_ids = config["attack_plan_ids"]
            n_plans = len(attack_plan_ids)

            total_weight = (
                (0 if playbook_id else W_PLAYBOOK)
                + n_plans * W_SIM
                + n_plans * W_ANALYSIS
                + W_PERSIST
                + W_SYNTH
            )
            progress = 0
            self._update_job_status(
                job_id, progress_current=0, progress_total=total_weight,
            )
            progress_lock = asyncio.Lock()

            async def bump(weight: int) -> None:
                nonlocal progress
                async with progress_lock:
                    progress += weight
                    self._update_job_status(job_id, progress_current=progress)

            # 1. Get or generate the playbook
            self._set_phase(job_id, "playbook")
            if playbook_id:
                playbook = self._kb.defense_playbooks.get(playbook_id)
                if not playbook:
                    raise ValueError(f"Playbook {playbook_id} not found")
            else:
                playbook = await self._pb_gen.generate(
                    settings,
                    self._kb.doctrine.list_active(settings.settings_id),
                    [],
                    config.get("extra_playbook_prompt", ""),
                )
                self._kb.defense_playbooks.save(playbook)
                await bump(W_PLAYBOOK)

            # 2. Pre-fetch all attack plans (DB in main process only)
            plans = []
            for plan_id in attack_plan_ids:
                plan = self._kb.attack_plans.get(plan_id)
                if plan:
                    plans.append(plan)
            if not plans:
                raise ValueError("No valid attack plans found")

            # 3. Run simulations in parallel across N CPU cores
            self._set_phase(job_id, "simulating")
            loop = asyncio.get_running_loop()
            max_workers = max(1, (os.cpu_count() or 4) - 1)
            sim_args = [(settings, p, playbook) for p in plans]
            plan_by_match_id: dict[str, object] = {}

            matches: list[MatchResult] = []
            takeaways_collected: list[tuple[str, AITakeaway]] = []

            with ProcessPoolExecutor(max_workers=max_workers) as pool:
                futures = [
                    loop.run_in_executor(pool, _run_one_sim, args)
                    for args in sim_args
                ]
                for i, fut in enumerate(futures):
                    match: MatchResult = await fut
                    plan = plans[i]
                    plan_by_match_id[match.match_id] = plan
                    matches.append(match)
                    await bump(W_SIM)

            # 4. Analyze all matches in parallel (LLM calls async-gathered).
            # Each task bumps progress as it finishes so the bar keeps moving
            # even though gather() resolves only when all have completed.
            self._set_phase(job_id, "analyzing")

            async def _analyze(match: MatchResult, plan) -> None:
                try:
                    analysis, takeaways = await self._analyzer.analyze(
                        match, plan.name, playbook.name,
                    )
                    match.ai_analysis_text = analysis
                    match.ai_takeaways = takeaways
                    match.analysis_completed_at = _now()
                    for t in takeaways:
                        takeaways_collected.append((match.match_id, t))
                except Exception as e:
                    match.ai_analysis_text = f"[Analysis failed: {e}]"
                await bump(W_ANALYSIS)

            await asyncio.gather(*[
                _analyze(m, plan_by_match_id[m.match_id]) for m in matches
            ])

            # 5. Persist match results + update champion pointers
            self._set_phase(job_id, "persisting")
            for match in matches:
                self._kb.match_results.upsert(match)
                self._kb.attack_patterns.update_champion(
                    match.pattern_id,
                    match.match_id,
                    match.defense_playbook_id,
                    match.fitness_score,
                )
            await bump(W_PERSIST)

            # 6. Synthesize doctrine updates
            self._set_phase(job_id, "synthesizing")
            doctrine_updates = {}
            try:
                existing_doctrine = self._kb.doctrine.list_active(settings.settings_id)
                doctrine_updates = await self._synth.synthesize(
                    settings_id=settings.settings_id,
                    existing_doctrine=existing_doctrine,
                    recent_takeaways=takeaways_collected[:50],
                )
                self._apply_doctrine_updates(
                    settings.settings_id,
                    doctrine_updates,
                )
            except Exception as e:
                doctrine_updates = {"error": str(e)}
            await bump(W_SYNTH)

            # 7. Complete job
            summary = {
                "phase": "completed",
                "playbook_id": playbook.playbook_id,
                "matches_created": [m.match_id for m in matches],
                "total_matches": len(matches),
                "wins": sum(1 for m in matches if m.outcome.value == "WIN"),
                "losses": sum(1 for m in matches if m.outcome.value == "LOSS"),
                "timeouts": sum(1 for m in matches if m.outcome.value == "TIMEOUT"),
                "avg_fitness": (
                    sum(m.fitness_score for m in matches) / len(matches)
                    if matches else 0.0
                ),
                "doctrine_updates": {
                    "additions": len(doctrine_updates.get("additions", [])),
                    "reinforcements": len(doctrine_updates.get("reinforcements", [])),
                    "supersessions": len(doctrine_updates.get("supersessions", [])),
                },
            }
            self._update_job_status(
                job_id,
                status="completed",
                progress_current=total_weight,
                result_summary=summary,
                completed_at=_now(),
            )

        except Exception as e:
            self._update_job_status(
                job_id,
                status="failed",
                error_message=str(e),
                completed_at=_now(),
            )

    def _apply_doctrine_updates(self, settings_id: str, updates: dict) -> None:
        for add in updates.get("additions", []):
            entry = DoctrineEntry(
                entry_id=f"doc-{uuid.uuid4().hex[:8]}",
                settings_id=settings_id,
                category=add.get("category", "general"),
                principle_text=add.get("principle_text", ""),
                trigger_conditions=add.get("trigger_conditions", {}),
                supporting_match_ids=add.get("supporting_match_ids", []),
                confidence_score=add.get("confidence_score", 0.5),
                version=1,
                is_active=True,
                created_at=_now(),
                updated_at=_now(),
            )
            self._kb.doctrine.save(entry)

        for reinforcement in updates.get("reinforcements", []):
            entry = self._kb.doctrine.get(reinforcement.get("entry_id", ""))
            if entry:
                entry.supporting_match_ids.extend(
                    reinforcement.get("new_supporting_match_ids", [])
                )
                if "new_confidence" in reinforcement:
                    entry.confidence_score = reinforcement["new_confidence"]
                entry.updated_at = _now()
                self._kb.doctrine.save(entry)

        for supersession in updates.get("supersessions", []):
            old_id = supersession.get("old_entry_id")
            if not old_id:
                continue
            old_entry = self._kb.doctrine.get(old_id)
            if not old_entry:
                continue
            new_entry = DoctrineEntry(
                entry_id=f"doc-{uuid.uuid4().hex[:8]}",
                settings_id=settings_id,
                category=old_entry.category,
                principle_text=supersession.get("new_principle_text", old_entry.principle_text),
                trigger_conditions=supersession.get("new_trigger_conditions", {}),
                supporting_match_ids=[],
                confidence_score=0.6,
                version=old_entry.version + 1,
                parent_entry_id=old_id,
                is_active=True,
                created_at=_now(),
                updated_at=_now(),
            )
            self._kb.doctrine.supersede(old_id, new_entry)

    def _set_phase(self, job_id: str, phase: str) -> None:
        """Merge a `phase` marker into result_summary_json for live UI labels."""
        session = get_session()
        try:
            m = session.query(TrainingJobModel).get(job_id)
            if not m:
                return
            existing = json.loads(m.result_summary_json) if m.result_summary_json else {}
            existing["phase"] = phase
            m.result_summary_json = json.dumps(existing)
            session.commit()
        finally:
            session.close()

    def _update_job_status(
        self,
        job_id: str,
        status: str | None = None,
        progress_current: int | None = None,
        progress_total: int | None = None,
        result_summary: dict | None = None,
        completed_at: str | None = None,
        error_message: str | None = None,
    ) -> None:
        session = get_session()
        try:
            m = session.query(TrainingJobModel).get(job_id)
            if not m:
                return
            if status:
                m.status = status
            if progress_current is not None:
                m.progress_current = progress_current
            if progress_total is not None:
                m.progress_total = progress_total
            if result_summary is not None:
                m.result_summary_json = json.dumps(result_summary)
            if completed_at is not None:
                m.completed_at = completed_at
            if error_message is not None:
                m.error_message = error_message
            session.commit()
        finally:
            session.close()
