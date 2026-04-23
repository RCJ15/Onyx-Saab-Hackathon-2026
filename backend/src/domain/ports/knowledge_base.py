from __future__ import annotations

from abc import ABC, abstractmethod

from ..value_objects.attack_pattern import AttackPattern
from ..value_objects.attack_plan import AttackPlan
from ..value_objects.defense_playbook import DefensePlaybook
from ..value_objects.doctrine_entry import DoctrineEntry
from ..value_objects.match_result import MatchResult
from ..value_objects.settings import Settings


class SettingsRepositoryPort(ABC):
    @abstractmethod
    def save(self, settings: Settings) -> str: ...
    @abstractmethod
    def get(self, settings_id: str) -> Settings | None: ...
    @abstractmethod
    def list_all(self) -> list[Settings]: ...
    @abstractmethod
    def get_active(self) -> Settings | None: ...
    @abstractmethod
    def set_active(self, settings_id: str) -> None: ...
    @abstractmethod
    def delete(self, settings_id: str) -> bool: ...


class AttackPlanRepositoryPort(ABC):
    @abstractmethod
    def save(self, plan: AttackPlan) -> str: ...
    @abstractmethod
    def get(self, plan_id: str) -> AttackPlan | None: ...
    @abstractmethod
    def list_by_settings(self, settings_id: str) -> list[AttackPlan]: ...
    @abstractmethod
    def list_by_pattern(self, pattern_id: str) -> list[AttackPlan]: ...
    @abstractmethod
    def count_by_settings(self, settings_id: str) -> int: ...
    @abstractmethod
    def delete(self, plan_id: str) -> bool: ...


class AttackPatternRepositoryPort(ABC):
    @abstractmethod
    def upsert(self, pattern: AttackPattern) -> str: ...
    @abstractmethod
    def get(self, pattern_id: str) -> AttackPattern | None: ...
    @abstractmethod
    def list_by_settings(self, settings_id: str) -> list[AttackPattern]: ...
    @abstractmethod
    def count_by_settings(self, settings_id: str) -> int: ...
    @abstractmethod
    def update_champion(
        self,
        pattern_id: str,
        match_id: str,
        playbook_id: str,
        fitness: float,
    ) -> None: ...


class DefensePlaybookRepositoryPort(ABC):
    @abstractmethod
    def save(self, playbook: DefensePlaybook) -> str: ...
    @abstractmethod
    def get(self, playbook_id: str) -> DefensePlaybook | None: ...
    @abstractmethod
    def list_by_settings(self, settings_id: str) -> list[DefensePlaybook]: ...
    @abstractmethod
    def count_by_settings(self, settings_id: str) -> int: ...
    @abstractmethod
    def delete(self, playbook_id: str) -> bool: ...
    @abstractmethod
    def rename(self, playbook_id: str, name: str) -> bool: ...


class MatchResultRepositoryPort(ABC):
    @abstractmethod
    def upsert(self, match: MatchResult) -> str: ...
    @abstractmethod
    def get(self, match_id: str) -> MatchResult | None: ...
    @abstractmethod
    def list_by_pattern(self, pattern_id: str, top_k: int = 5) -> list[MatchResult]: ...
    @abstractmethod
    def list_by_attack_plan(self, attack_plan_id: str) -> list[MatchResult]: ...
    @abstractmethod
    def list_by_playbook(self, playbook_id: str) -> list[MatchResult]: ...
    @abstractmethod
    def list_by_settings(
        self, settings_id: str, limit: int = 100
    ) -> list[MatchResult]: ...


class DoctrineRepositoryPort(ABC):
    @abstractmethod
    def save(self, entry: DoctrineEntry) -> str: ...
    @abstractmethod
    def get(self, entry_id: str) -> DoctrineEntry | None: ...
    @abstractmethod
    def list_active(
        self, settings_id: str, category: str | None = None
    ) -> list[DoctrineEntry]: ...
    @abstractmethod
    def list_versions(self, settings_id: str, category: str) -> list[DoctrineEntry]: ...
    @abstractmethod
    def count_active_by_settings(self, settings_id: str) -> int: ...
    @abstractmethod
    def supersede(self, old_entry_id: str, new_entry: DoctrineEntry) -> str: ...
    @abstractmethod
    def rename(self, entry_id: str, name: str, updated_at: str) -> bool: ...


class KnowledgeBasePort(ABC):
    """
    Aggregator port combining all knowledge-base operations.
    Implementations wire together the individual repos.
    """
    settings: SettingsRepositoryPort
    attack_plans: AttackPlanRepositoryPort
    attack_patterns: AttackPatternRepositoryPort
    defense_playbooks: DefensePlaybookRepositoryPort
    match_results: MatchResultRepositoryPort
    doctrine: DoctrineRepositoryPort
