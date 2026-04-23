const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ==== Types ====

export interface Settings {
  settings_id: string;
  name: string;
  tick_minutes: number;
  max_ticks: number;
  created_at: string;
  notes: string;
  is_active: boolean;
}

export interface SettingsDetail extends Settings {
  scenario: Record<string, unknown>;
  defender_resources: Record<string, Record<string, number>>;
  attacker_resources: Record<string, Record<string, number>>;
  engagement_params: Record<string, unknown>;
}

export interface AttackAction {
  tick: number;
  type: string;
  aircraft_type: string;
  count: number;
  from_base?: string | null;
  target?: {
    type: string;
    id?: string | null;
    x_km?: number | null;
    y_km?: number | null;
  } | null;
  abort_conditions?: {
    p_success_threshold: number;
    jettison_weapons_on_abort: boolean;
  };
}

export interface AttackPlan {
  plan_id: string;
  settings_id: string;
  pattern_id: string | null;
  name: string;
  description: string;
  source: string;
  tags: string[];
  actions: AttackAction[];
  created_at: string;
}

export interface DefensePlaybook {
  playbook_id: string;
  settings_id: string;
  name: string;
  description: string;
  source: string;
  doctrine_notes: string;
  standing_orders: Array<Record<string, unknown>>;
  triggers: Array<Record<string, unknown>>;
  constraints: Record<string, unknown>;
  created_at: string;
}

export interface SimulationMetrics {
  total_civilian_casualties: number;
  time_to_first_casualty: number | null;
  cities_defended: number;
  capital_survived: boolean;
  aircraft_lost: number;
  aircraft_remaining: number;
  aircraft_damaged_in_repair: number;
  bases_lost: number;
  bases_remaining: number;
  parked_aircraft_destroyed: number;
  total_engagements: number;
  engagements_won: number;
  engagement_win_rate: number;
  missiles_fired: number;
  missiles_hit: number;
  enemy_sorties_deterred: number;
  enemy_weapons_jettisoned: number;
  enemy_mission_kills: number;
  air_denial_score: number;
  sorties_flown: number;
  fuel_efficiency: number;
  response_time_avg: number;
  total_ticks: number;
}

export interface MatchResult {
  match_id: string;
  settings_id: string;
  attack_plan_id: string;
  pattern_id: string;
  defense_playbook_id: string;
  outcome: string;
  fitness_score: number;
  metrics: SimulationMetrics;
  ai_analysis_text: string;
  ai_takeaways: Array<{
    principle: string;
    confidence: number;
    tags: string[];
    supporting_tick_refs: number[];
  }>;
  total_ticks?: number;
  created_at?: string;
  analysis_completed_at?: string | null;
}

export interface ReplayTick {
  tick: number;
  aircraft: Array<Record<string, unknown>>;
  locations: Array<Record<string, unknown>>;
  events: Array<Record<string, unknown>>;
}

export interface Replay {
  match_id: string;
  outcome: string;
  total_ticks: number;
  ticks: ReplayTick[];
  metrics: SimulationMetrics;
}

export interface TrainingJob {
  job_id: string;
  settings_id: string;
  status: string;
  progress_current: number;
  progress_total: number;
  started_at: string;
  completed_at: string | null;
  result_summary: {
    phase?: "playbook" | "simulating" | "analyzing" | "persisting" | "synthesizing" | "completed";
    playbook_id?: string;
    matches_created?: string[];
    total_matches?: number;
    wins?: number;
    losses?: number;
    timeouts?: number;
    avg_fitness?: number;
    doctrine_updates?: { additions: number; reinforcements: number; supersessions: number };
  } | null;
  error?: string | null;
}

export interface AttackPattern {
  pattern_id: string;
  settings_id: string;
  canonical_description: string;
  feature_tags: string[];
  force_composition: Record<string, number>;
  target_profile: string;
  wave_count: number;
  total_plans_count: number;
  total_matches_count: number;
  best_defense_playbook_id: string | null;
  best_fitness_score: number | null;
  best_match_id: string | null;
}

export interface DoctrineEntry {
  entry_id: string;
  settings_id: string;
  category: string;
  name: string;
  principle_text: string;
  trigger_conditions: Record<string, unknown>;
  supporting_match_ids: string[];
  confidence_score: number;
  version: number;
  is_active: boolean;
  human_edited: boolean;
  created_at: string;
  updated_at: string;
}

// ==== Fetch helpers ====

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json();
}

// ==== Settings ====

export const listSettings = () =>
  fetchAPI<{ settings: Settings[]; active_id: string | null }>("/settings");
export const getActiveSettings = () => fetchAPI<SettingsDetail>("/settings/active");
export const getSettings = (id: string) => fetchAPI<SettingsDetail>(`/settings/${id}`);
export const createSettingsFromScenario = (params: { name: string; scenario_path?: string; notes?: string }) =>
  fetchAPI<Settings>("/settings/from-scenario", { method: "POST", body: JSON.stringify(params) });
export const activateSettings = (id: string) =>
  fetchAPI<{ activated: string }>(`/settings/${id}/activate`, { method: "POST" });
export const deleteSettings = (id: string) =>
  fetchAPI<{ deleted: string }>(`/settings/${id}`, { method: "DELETE" });
export const resetAllData = () =>
  fetchAPI<{ reset: boolean }>("/settings/reset-all", { method: "POST" });

// ==== Attack plans ====

export const listAttackPlans = () =>
  fetchAPI<{ plans: AttackPlan[]; total: number }>("/attack-plans");
export const getAttackPlan = (id: string) =>
  fetchAPI<AttackPlan>(`/attack-plans/${id}`);
export const generateRandomAttack = (count: number, base_seed: number = 1) =>
  fetchAPI<{ generated: number; plans: AttackPlan[] }>("/attack-plans/generate-random", {
    method: "POST",
    body: JSON.stringify({ count, base_seed }),
  });
export const generateAIAttack = (prompt: string) =>
  fetchAPI<AttackPlan>("/attack-plans/generate-ai", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
export const deleteAttackPlan = (id: string) =>
  fetchAPI<{ deleted: string }>(`/attack-plans/${id}`, { method: "DELETE" });

// ==== Defense playbooks ====

export const listPlaybooks = () =>
  fetchAPI<{ playbooks: DefensePlaybook[]; total: number }>("/defense-playbooks");
export const getPlaybook = (id: string) =>
  fetchAPI<DefensePlaybook>(`/defense-playbooks/${id}`);
export const generateAIPlaybook = (prompt: string = "", similar_to_pattern_id?: string) =>
  fetchAPI<DefensePlaybook>("/defense-playbooks/generate-ai", {
    method: "POST",
    body: JSON.stringify({ prompt, similar_to_pattern_id: similar_to_pattern_id ?? null }),
  });
export const createBaselinePlaybook = () =>
  fetchAPI<DefensePlaybook>("/defense-playbooks/create-baseline", { method: "POST" });
export const deletePlaybook = (id: string) =>
  fetchAPI<{ deleted: string }>(`/defense-playbooks/${id}`, { method: "DELETE" });

// ==== Evaluation ====

export const runEvaluation = (params: {
  attack_plan_id: string;
  defense_playbook_id: string;
  analyze?: boolean;
  live_commander?: boolean;
}) =>
  fetchAPI<MatchResult>("/evaluation/run", {
    method: "POST",
    body: JSON.stringify({ analyze: false, live_commander: false, ...params }),
  });

export const getMatch = (id: string) =>
  fetchAPI<MatchResult>(`/evaluation/matches/${id}`);
export const getReplay = (id: string) =>
  fetchAPI<Replay>(`/evaluation/matches/${id}/replay`);
export const listMatches = (limit: number = 50) =>
  fetchAPI<{ matches: Array<Record<string, unknown>>; total: number }>(
    `/evaluation/matches?limit=${limit}`,
  );

// ==== Training ====

export const startTraining = (params: {
  attack_plan_ids: string[];
  defense_playbook_id?: string | null;
  extra_playbook_prompt?: string;
}) =>
  fetchAPI<{ job_id: string; status: string }>("/training/start", {
    method: "POST",
    body: JSON.stringify(params),
  });
export const getTrainingJob = (id: string) =>
  fetchAPI<TrainingJob>(`/training/jobs/${id}`);
export const listTrainingJobs = () =>
  fetchAPI<{ jobs: TrainingJob[] }>("/training/jobs");

// ==== Knowledge ====

export interface KnowledgeBundle {
  settings_id: string;
  settings_name: string;
  counts: Record<string, number>;
  doctrine: DoctrineEntry[];
  patterns: AttackPattern[];
  playbooks: DefensePlaybook[];
  matches: Array<Record<string, unknown>>;
}

export const getKnowledgeBundle = (matches_limit: number = 50) =>
  fetchAPI<KnowledgeBundle>(`/knowledge/bundle?matches_limit=${matches_limit}`);

export const getKnowledgeSummary = () =>
  fetchAPI<{ settings_id: string; settings_name: string; counts: Record<string, number> }>(
    "/knowledge/summary",
  );
export const listDoctrine = (category?: string) =>
  fetchAPI<{ entries: DoctrineEntry[]; total: number }>(
    category ? `/knowledge/doctrine?category=${category}` : "/knowledge/doctrine",
  );
export const renameDoctrine = (entry_id: string, name: string) =>
  fetchAPI<{ entry_id: string; name: string; updated_at: string }>(
    `/knowledge/doctrine/${entry_id}/name`,
    { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) },
  );
export const renamePlaybook = (playbook_id: string, name: string) =>
  fetchAPI<{ playbook_id: string; name: string }>(
    `/defense-playbooks/${playbook_id}/name`,
    { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) },
  );
export const listPatterns = () =>
  fetchAPI<{ patterns: AttackPattern[]; total: number }>("/knowledge/patterns");
export const listPatternMatches = (pattern_id: string, top_k: number = 10) =>
  fetchAPI<{ matches: Array<Record<string, unknown>> }>(
    `/knowledge/patterns/${pattern_id}/matches?top_k=${top_k}`,
  );
