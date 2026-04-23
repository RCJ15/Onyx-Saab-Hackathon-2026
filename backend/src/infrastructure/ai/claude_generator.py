from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

import httpx

from src.domain.entities.attack_plan import AttackPlan, AttackPlanSource

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You are a military attack planner AI for a simulation engine. You generate attack plans as JSON.

## Context
Two countries separated by a strait ("The Boreal Passage"). The ATTACKER is Country Y (south).

ATTACKER BASES (south):
- firewatch_station: position [1398.3, 1071.7], capacity 12
- southern_redoubt: position [321.7, 1238.3], capacity 15
- spear_point_base: position [918.3, 835.0], capacity 8

DEFENDER TARGETS (north):
- arktholm (CAPITAL): position [418.3, 95.0], population 500,000
- valbrek (city): position [1423.3, 213.3], population 120,000
- nordvik (city): position [140.0, 323.3], population 150,000
- northern_vanguard (base): position [198.3, 335.0]
- highridge_command (base): position [838.3, 75.0]
- boreal_watch_post (base): position [1158.3, 385.0]

AIRCRAFT TYPES (available to attacker):
- bomber: slow (600km/h), high payload, deals city damage, weak in air combat
- combat_plane: fast (900km/h), strong in dogfights
- uav: medium speed (250km/h), moderate combat
- drone_swarm: slow (150km/h), cheap, good vs bombers

AVAILABLE ACTIONS per step:
- launch: Launch aircraft from a base toward a target
- rtb: Return to base
- patrol: Patrol an area
- intercept_zone: Move to intercept near a zone
- regroup: All return to home bases
- hold: Stay in current position

## Rules
- Tick = 5 minutes of real time. Max 1000 ticks (83 hours).
- Aircraft need fuel. Plan RTB waves or they crash.
- bombers are the only type that damages cities.
- combat_planes are the best air-to-air fighters.

## Output Format
Return ONLY valid JSON, no markdown:
{
  "name": "Plan name",
  "description": "Brief tactical description",
  "tags": ["tag1", "tag2"],
  "actions": [
    {
      "tick": 1,
      "type": "launch",
      "aircraft_type": "bomber",
      "count": 3,
      "from_base": "firewatch_station",
      "target": {"type": "city", "id": "arktholm", "x_km": 418.3, "y_km": 95.0}
    }
  ]
}
"""


async def generate_attack_plan_with_claude(prompt: str) -> AttackPlan:
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set")

    model = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-6")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            OPENROUTER_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 4096,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        if response.status_code >= 400:
            raise ValueError(
                f"OpenRouter API {response.status_code}: {response.text}"
            )
        data = response.json()

    # Extract text content
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""

    # Parse JSON from response (handle possible markdown wrapping)
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    plan_data = json.loads(text)
    plan_id = f"ai-{uuid.uuid4().hex[:8]}"
    plan_data["id"] = plan_id
    plan_data["source"] = "ai_generated"
    plan_data["created_at"] = datetime.now(timezone.utc).isoformat()
    if "tags" not in plan_data:
        plan_data["tags"] = ["ai_generated"]
    else:
        plan_data["tags"].append("ai_generated")

    return AttackPlan.from_dict(plan_data)
