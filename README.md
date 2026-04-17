# Boreal Passage — LLM-Driven Air Defense Simulator

> SAAB × KTH Hackathon · April 2026
>
> A tactical air defense simulator where an LLM-powered commander accumulates doctrine through simulated combat, then defends the airspace in real time against novel attacks — auditable and editable by human officers.

---

## The One-Line Pitch

Generate attacks, simulate combat as ground truth, have an LLM extract tactical doctrine from the outcomes, and use that doctrine to make real-time defense decisions against new attacks — with human officers in the loop to audit, edit, and compete.

---

## Why This Matters

Traditional training-based approaches (Deep RL, evolutionary algorithms) need millions of simulations, opaque neural weights, and heavy compute. They also produce "black box" policies that military decision-makers can't read or trust.

We use LLMs instead. The LLM's pretraining already encodes vast tactical knowledge. We treat the simulation as the **ground truth judge**, not as training data. The LLM generates hypotheses (attack plans, defense playbooks), the simulation scores them, and the LLM reflects on what worked and why — building up a **human-readable doctrine document** and a **case library** of proven tactics.

The result: a defense system that can be read, understood, corrected, and co-designed by real air defense officers — that still outperforms unaided humans.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    THE LEARNING LOOP (Coach Mode)                │
│                                                                  │
│   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐     │
│   │    LLM      │      │ SIMULATION  │      │    LLM      │     │
│   │  generates  ├─────>│   judges    ├─────>│   reflects  │     │
│   │  candidates │      │(deterministic│      │ on outcomes │     │
│   └─────────────┘      │ ground truth)│      └──────┬──────┘     │
│         ▲              └─────────────┘             │             │
│         │                                          ▼             │
│         │                                  ┌─────────────┐      │
│         │                                  │ KNOWLEDGE   │      │
│         └──────────────────────────────────┤    BASE     │      │
│                  retrieved as context      │  (doctrine  │      │
│                                            │  + cases)   │      │
│                                            └──────┬──────┘      │
└───────────────────────────────────────────────────┼─────────────┘
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                  REAL-TIME DEFENSE (Evaluate Mode)               │
│                                                                  │
│   New attack ──> LLM reads doctrine + similar cases ──>          │
│      Generates defense playbook ──> Simulation runs it ──>       │
│        Deterministic outcome: WIN / LOSS with full metrics       │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Three-Layer Architecture

What happens during a simulation is split across three layers with clear responsibilities. Critically, **the LLM is never inside the simulation loop** — every simulation is pure, deterministic Python.

### Layer 1 — Physics & Mechanics
Deterministic simulation: aircraft movement, fuel consumption, damage propagation, multi-step BVR missile engagement (detection → salvo → evasion → damage roll → disengagement).

### Layer 2 — Pilot Reflexes (autonomous aircraft behavior)
Hardcoded realistic behaviors that run per aircraft per tick:
- Abort mission if P(success) < 0.35 (e.g. bomber intercepted far from target)
- RTB at bingo fuel
- Evade if missile locked on
- Bug out if outnumbered with bad geometry
- Jettison weapons if forced to evade (bombers)

This layer produces **emergent deterrence** — a bomber aborts when our fighters arrive, without anyone scripting it.

### Layer 3 — Commander (the "intelligence")
Higher-level decisions from either:
- An **attack plan** (timeline of launches with abort parameters), OR
- A **defense playbook** (standing orders + reactive triggers + constraints)

The LLM writes these in JSON. The simulation executes them deterministically.

---

## Attack Plans vs Defense Playbooks — Deliberate Asymmetry

Attacker controls the tempo; their plan is mostly a timeline. Defender is reactive; their playbook is a ruleset.

**Attack plan (timeline):**
```json
{
  "id": "atk-abc",
  "actions": [
    {"tick": 1, "type": "launch", "count": 4, "aircraft_type": "bomber",
     "from_base": "firewatch_station", "target": "arktholm",
     "abort_conditions": {"p_success_threshold": 0.35}},
    {"tick": 30, "type": "launch", "count": 8, "aircraft_type": "drone_swarm",
     "from_base": "spear_point_base", "target": "nordvik"}
  ]
}
```

**Defense playbook (reactive ruleset):**
```json
{
  "id": "def-xyz",
  "standing_orders": [
    {"name": "cap_over_capital", "type": "patrol", "count": 2,
     "zone": {"center": "arktholm", "radius_km": 80}}
  ],
  "triggers": [
    {"when": "bomber_detected_within_km_of_city(400)",
     "action": "scramble_intercept(count=3, from=nearest_ready)",
     "priority": 10}
  ],
  "constraints": {
    "reserve_fraction": 0.30,
    "never_leave_capital_uncovered": true
  },
  "doctrine_notes": "Engage bombers at standoff range. Drones vs drones, fighters vs anything with a missile."
}
```

Both generated by Claude. Both stored as JSON. Both readable by humans.

---

## The Knowledge Base

As simulations run, the system accumulates three persistent artifacts — this is where "learning" happens, and none of it requires gradient descent.

### 1. Doctrine Document (markdown)
An evolving document of tactical principles, authored by the LLM after each reflection round.

```markdown
# Defense Doctrine — v12

## Primary Principles
1. Capital (Arktholm) is the non-negotiable asset
2. Maintain minimum 30% reserve at all times
3. Engage bombers at 300+ km from defended cities

## Against Multi-Wave Attacks
- Commit no more than 40% to the first wave
- Hold combat planes in reserve for bomber waves 2-3
- Drone swarms at the east strait are usually a feint — do not chase

## Known Failure Modes
- Over-committing west when Valbrek is the real target
- Refueling all aircraft simultaneously (fuel bottleneck at base)
```

**Humans can edit this directly.** It's version-controlled. The LLM respects their edits.

### 2. Case Library
Every simulation produces a case: `(attack_plan, defense_playbook, outcome, metrics, reflection)`. Stored in SQLite with text summaries indexed for BM25 retrieval.

When the LLM needs to generate a new defense, it retrieves the top-K most similar past cases: "Last time an attack like this happened, here's what worked and why."

### 3. Reflections
After each coach iteration, the LLM compares top performers vs worst performers and writes specific lessons:

> *"Defenses that kept a 2-ship CAP over Arktholm won 87% of matchups. Flooding interceptors forward lost the capital in 41%. Lesson: geometric positioning > aircraft count for multi-wave attacks."*

That lesson becomes a paragraph in the doctrine.

---

## Deterministic Simulation — Why & How

Combat is richly probabilistic internally (missile Pk, damage rolls, deterrence checks) — but we seed the RNG deterministically from `(attack_plan_id, defense_playbook_id, scenario_id)`.

Consequence: same attack + same defense = same outcome, always. Every time.

Why this matters:
- **Case library is clean** — one row per matchup, not a distribution
- **Coach loop is fast** — no need for 20+ seeds per evaluation
- **Robustness comes from plan diversity**, not seed variance — a defense is "good" because it beats many *different* attacks, not because it probabilistically wins a single matchup
- **Reproducibility is free** — paste a replay link, anyone gets the same simulation

---

## The Demo Scenario: AI vs Human Officer

The killer demo we're building toward:

1. **Load an unseen attack plan** (AI-generated, never been simulated before)
2. **Run it against our trained defense playbook** — simulation shows the outcome with metrics + replay
3. **Load the same attack into an interactive UI where a human air defense officer controls the defense** — the human makes their best decisions
4. **Compare the outcomes.** Same resources, same attack, different commanders
5. **Show the human the AI's doctrine document.** Let them edit a rule they disagree with
6. **Retrain the coach loop** with the human-edited doctrine as the starting point
7. **Repeat.** Over iterations, the coached AI surpasses unaided human performance — and the human learns from the AI too

---

## Scenario: The Boreal Passage

Two countries separated by a ~400 km maritime strait.

| Country X (North, defender) | Country Y (South, attacker) |
|---|---|
| Capital: **Arktholm** (pop. 500K) | Capital: Meridia (pop. 450K) |
| Cities: Nordvik, Valbrek | Cities: Callhaven, Solano |
| Bases: Northern Vanguard, Highridge Command, Boreal Watch Post | Bases: Firewatch Station, Southern Redoubt, Spear Point Base |

Theater: 1667 km × 1300 km. Aircraft types: combat plane (Gripen-like), bomber (Su-34-like), UAV (MQ-9-like), drone swarm (Shahed/Switchblade-like). Real aircraft parameters researched with 30+ sources — see [research/](research/).

Country X (defender) is modeled on **Swedish Air Force doctrine**: BAS 90 dispersed basing, Gripen's 10-minute turnaround, air denial instead of air superiority.

---

## KPIs Tracked per Simulation

```
total_civilian_casualties
time_to_first_casualty
aircraft_lost
aircraft_remaining
bases_lost
bases_remaining
cities_defended
capital_survived
total_ticks
fuel_efficiency
engagement_win_rate
response_time_avg
total_engagements
sorties_flown
```

Upcoming (with realistic engagement model):
```
enemy_sorties_deterred        # aborted before reaching target
enemy_weapons_jettisoned      # bombers forced to drop payload
mission_kills_forced          # damaged but not destroyed
damaged_aircraft_rtb          # returning wounded
air_denial_score              # fraction of enemy sorties that failed
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Simulation engine | Python 3.12, pure stdlib, `ProcessPoolExecutor` parallelism |
| Backend API | FastAPI, Pydantic, SQLAlchemy (SQLite) |
| Frontend | Next.js 16, React, TypeScript, Canvas 2D |
| LLM | Claude Sonnet 4.6 via Anthropic API |
| Deployment | Docker Compose (2 services) |
| Architecture | Hexagonal (Ports & Adapters) — domain has zero external dependencies |

---

## Project Structure

```
├── CLAUDE.md                      # Entry point for coding agents
├── Development/                   # All development guides
│   ├── ARCHITECTURE.md            # Hexagonal architecture rules
│   ├── DOMAIN.md                  # Entities, value objects, combat rules
│   ├── SIMULATION.md              # Tick model, parallelism, replay format
│   ├── API.md                     # REST + WebSocket spec
│   ├── RESEARCH.md                # How to document research
│   ├── CONTRIBUTING.md            # Code style, git workflow, how-tos
│   └── Implementation/            # Per-feature implementation guides
├── research/                      # 6 research documents, 150+ sources
├── scenario/                      # Scenario configs + hardcoded baseline strategies
├── backend/                       # Python simulation engine + API
│   └── src/
│       ├── domain/                # Pure business logic (zero external deps)
│       ├── application/           # Use cases
│       └── infrastructure/        # Adapters: FastAPI, SQLite, Claude API
├── frontend/                      # Next.js admin console
│   └── src/
│       ├── app/                   # Pages: /, /evaluate, /training, /plans
│       └── components/mil/        # Military-themed UI primitives
├── data/                          # SQLite DB (gitignored)
└── docker-compose.yml
```

---

## Quick Start

```bash
cp .env.example .env
# Edit .env and add: ANTHROPIC_API_KEY=sk-ant-...your-key...

docker compose up --build
```

- **UI**: http://localhost:3000
- **API docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health

### First flow to test

1. Visit **/plans** → click **"GENERATE 10 RANDOM PLANS"** to seed the attack library
2. Visit **/evaluate** → pick a plan, run a single simulation, watch the replay
3. Visit **/training** → select all plans, run tournament mode, see per-plan defense success

---

## Current Status (Phase 1 complete, Phase 2 in design)

### ✅ Phase 1 — Foundation (shipped)
- Deterministic simulation engine with 8-phase tick loop
- Scenario configuration (Boreal Passage locations, aircraft, matchups)
- Attack plan JSON schema + scripted execution
- Claude API integration for AI attack plan generation
- 3 hardcoded defense strategies (defensive, aggressive, balanced)
- Admin console: Evaluate mode, Tournament mode, Plans library
- Docker Compose single-command deployment
- SQLite persistence for simulations + attack plans

### 🚧 Phase 2 — The Real Intelligence Layer (in design)
Research complete ([Development/Implementation/](Development/Implementation/)), implementation pending user approval:

- **Realistic engagement model** — multi-step BVR with 7 outcome types (hard kill, mission kill, damaged, evaded, disengaged, deterred, no engagement) instead of binary kill
- **Pilot reflexes (Layer 2)** — autonomous aircraft behaviors: abort on low P(success), RTB at bingo, jettison weapons when deterred
- **Defense playbook schema** — standing orders + triggers + constraints, symmetric with attack plans
- **Doctrine document + case library** — the knowledge base that grows with each coach iteration
- **Coach mode** — the iterative LLM loop: generate → simulate → reflect → persist
- **Research-backed aircraft parameters** — replacing placeholder stats with Gripen/F-16/F-35/Su-34/MQ-9/Shahed data (30+ sources)

### 🎯 Phase 3 — Human-in-the-Loop Demo
- Interactive UI for a human officer to command the defense live
- Side-by-side comparison: AI doctrine vs human decisions
- Human-editable doctrine with version history
- Tournament mode showing AI-coached > hardcoded baselines > naive human

---

## Research Foundation

Six documents in [research/](research/) with ~150 cited sources from NATO, RAND, CSBA, NATO RTO, DTIC, Jane's, manufacturer specs, and published conflict data (Gulf War, Ukraine, Falklands):

| Document | Focus |
|---|---|
| [aircraft_performance.md](research/aircraft_performance.md) | Speed, range, fuel, turnaround for real aircraft |
| [base_logistics.md](research/base_logistics.md) | Squadron sizes, fuel storage, sortie generation rates |
| [combat_probabilities.md](research/combat_probabilities.md) | Missile Pk by era and conflict |
| [air_defense_intercept_doctrine.md](research/air_defense_intercept_doctrine.md) | NATO QRA, BAS 90, ROE, air denial vs superiority |
| [engagement_outcomes.md](research/engagement_outcomes.md) | Multi-outcome combat model, Pk ranges, attrition |
| [strategy_optimization.md](research/strategy_optimization.md) | Optimization approach analysis (GA / BO / MCTS / RL) |

---

## Who's This For

- **SAAB engineers & advisors**: a credible, auditable defense AI that embodies Swedish doctrine and can be compared against human officers
- **KTH students & hackathon judges**: a novel architecture combining LLM agents, deterministic simulation, and hexagonal software design
- **Air defense officers**: a system whose reasoning they can read, challenge, and improve

---

## Team

Hackathon team · Apr 17–20, 2026

Architecture and dev environment led by Leo. Research and doctrine sourced from open-source defense publications.

---

## License

Built for the SAAB × KTH Hackathon 2026. Not intended for production or operational use.
