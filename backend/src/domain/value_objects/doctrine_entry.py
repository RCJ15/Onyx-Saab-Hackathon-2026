from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DoctrineEntry:
    """
    A single tactical principle in the knowledge base.

    Doctrine entries are LLM-authored but human-editable. Entries are
    versioned: updates insert a new row with parent_entry_id and deactivate
    the old one. History preserved.
    """
    entry_id: str
    settings_id: str
    category: str                                   # 'multi_wave_defense', 'bomber_counter', etc.
    principle_text: str                             # the lesson
    name: str = ""                                  # human-readable short title
    trigger_conditions: dict = field(default_factory=dict)  # when this applies
    supporting_match_ids: list[str] = field(default_factory=list)
    confidence_score: float = 0.5
    version: int = 1
    parent_entry_id: str | None = None
    is_active: bool = True
    human_edited: bool = False
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "settings_id": self.settings_id,
            "category": self.category,
            "name": self.name,
            "principle_text": self.principle_text,
            "trigger_conditions": self.trigger_conditions,
            "supporting_match_ids": self.supporting_match_ids,
            "confidence_score": self.confidence_score,
            "version": self.version,
            "parent_entry_id": self.parent_entry_id,
            "is_active": self.is_active,
            "human_edited": self.human_edited,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_dict(data: dict) -> "DoctrineEntry":
        return DoctrineEntry(
            entry_id=data["entry_id"],
            settings_id=data["settings_id"],
            category=data.get("category", "general"),
            name=data.get("name", ""),
            principle_text=data.get("principle_text", ""),
            trigger_conditions=data.get("trigger_conditions", {}),
            supporting_match_ids=data.get("supporting_match_ids", []),
            confidence_score=data.get("confidence_score", 0.5),
            version=data.get("version", 1),
            parent_entry_id=data.get("parent_entry_id"),
            is_active=data.get("is_active", True),
            human_edited=data.get("human_edited", False),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
