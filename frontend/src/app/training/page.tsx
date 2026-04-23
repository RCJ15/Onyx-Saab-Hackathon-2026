"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Header } from "@/components/mil/Header";
import { Panel, MetricRow } from "@/components/mil/Panel";
import {
  deleteAttackPlan,
  generateAIAttack,
  generateRandomAttack,
  getTrainingJob,
  listAttackPlans,
  listPlaybooks,
  listTrainingJobs,
  startTraining,
  type AttackPlan,
  type DefensePlaybook,
  type TrainingJob,
} from "@/lib/api";
import { invalidate } from "@/lib/cache";

type AttackGroup = {
  key: string;                // group identifier (tag-derived)
  label: string;              // human-readable name
  source: string;             // "random" | "ai_generated" | "custom"
  plans: AttackPlan[];
  createdAt: string;
};

function groupKeyOf(plan: AttackPlan): string {
  // Prefer an explicit "batch:*" tag; fall back to source + date bucket
  const batchTag = plan.tags.find((t) => t.startsWith("batch:"));
  if (batchTag) return batchTag;
  // Fallback: date-hour bucket by creation timestamp
  const bucket = plan.created_at.substring(0, 13); // "2026-04-20T14"
  return `${plan.source}:${bucket}`;
}

function groupLabel(key: string, plans: AttackPlan[]): string {
  if (key.startsWith("batch:")) return key.substring(6).replace(/-/g, " ");
  const [src, bucket] = key.split(":");
  const count = plans.length;
  const srcLabel = src === "ai_generated" ? "AI" : src === "random" ? "Random" : "Custom";
  const date = bucket?.replace("T", " ") ?? "";
  return `${srcLabel} batch — ${date}:00 (${count})`;
}

export default function TrainingPage() {
  const [plans, setPlans] = useState<AttackPlan[]>([]);
  const [playbooks, setPlaybooks] = useState<DefensePlaybook[]>([]);
  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [selectedPlans, setSelectedPlans] = useState<Set<string>>(new Set());
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);
  const [playbookId, setPlaybookId] = useState<string>("");
  const [extraPrompt, setExtraPrompt] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Attack generation form state
  const [genMode, setGenMode] = useState<"random" | "ai">("random");
  const [randomCount, setRandomCount] = useState(8);
  const [randomSeed, setRandomSeed] = useState(() => Date.now() % 10000);
  const [aiPrompt, setAiPrompt] = useState(
    "Generate a multi-wave bomber attack on Arktholm with drone swarms as feint on Nordvik.",
  );
  const [generating, setGenerating] = useState(false);

  // Active job state
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<TrainingJob | null>(null);
  const [starting, setStarting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = async () => {
    try {
      const [p, pb, j] = await Promise.all([
        listAttackPlans(),
        listPlaybooks(),
        listTrainingJobs(),
      ]);
      setPlans(p.plans);
      setPlaybooks(pb.playbooks);
      setJobs(j.jobs);
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  // Poll active job
  useEffect(() => {
    if (!activeJobId) return;
    const tick = async () => {
      try {
        const job = await getTrainingJob(activeJobId);
        setActiveJob(job);
        if (job.status === "completed" || job.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          invalidate("kb");            // KB data changed — bust cache
          refresh();
        }
      } catch (e) {
        setError(String(e));
      }
    };
    tick();
    pollRef.current = setInterval(tick, 2000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [activeJobId]);

  // Group plans by batch
  const groups: AttackGroup[] = useMemo(() => {
    const map = new Map<string, AttackPlan[]>();
    for (const p of plans) {
      const key = groupKeyOf(p);
      const arr = map.get(key) ?? [];
      arr.push(p);
      map.set(key, arr);
    }
    return Array.from(map.entries())
      .map(([key, arr]) => ({
        key,
        label: groupLabel(key, arr),
        source: arr[0].source,
        plans: arr.sort((a, b) => a.created_at.localeCompare(b.created_at)),
        createdAt: arr
          .map((p) => p.created_at)
          .sort()
          .reverse()[0] ?? "",
      }))
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  }, [plans]);

  const toggleGroup = (group: AttackGroup) => {
    setSelectedGroup(group.key);
    setSelectedPlans(new Set(group.plans.map((p) => p.plan_id)));
  };

  const togglePlan = (id: string) => {
    const next = new Set(selectedPlans);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedPlans(next);
    setSelectedGroup(null);
  };

  const selectAll = () => {
    setSelectedPlans(new Set(plans.map((p) => p.plan_id)));
    setSelectedGroup(null);
  };
  const clearSelection = () => {
    setSelectedPlans(new Set());
    setSelectedGroup(null);
  };

  const onGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      if (genMode === "random") {
        const res = await generateRandomAttack(randomCount, randomSeed);
        await refresh();
        // Auto-select the just-generated group
        const newIds = new Set(res.plans.map((p) => p.plan_id));
        setSelectedPlans(newIds);
        setRandomSeed((s) => s + randomCount + 1);
      } else {
        const res = await generateAIAttack(aiPrompt);
        await refresh();
        setSelectedPlans(new Set([res.plan_id]));
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setGenerating(false);
    }
  };

  const onStartTraining = async () => {
    if (selectedPlans.size === 0) return;
    setStarting(true);
    setError(null);
    try {
      const res = await startTraining({
        attack_plan_ids: Array.from(selectedPlans),
        defense_playbook_id: playbookId || null,
        extra_playbook_prompt: extraPrompt,
      });
      setActiveJobId(res.job_id);
      setActiveJob(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setStarting(false);
    }
  };

  const onDeletePlan = async (id: string) => {
    if (!confirm("Delete this attack plan?")) return;
    try {
      await deleteAttackPlan(id);
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 p-6 max-w-[1800px] mx-auto w-full">
        <div className="mb-6">
          <h1 className="mil-heading text-2xl mb-1">⚡ TRAIN</h1>
          <p className="text-dim text-sm tracking-wider">
            GENERATE ATTACK SETS → RUN TRAINING → DOCTRINE GROWS
          </p>
        </div>

        {error && (
          <div className="mil-panel mb-4 p-3 border-red-900/50">
            <span className="text-danger text-xs">⚠ {error}</span>
          </div>
        )}

        <div className="grid grid-cols-[380px_1fr] gap-4">
          {/* LEFT COLUMN: Generate + Start */}
          <div className="space-y-4">
            <Panel title="① GENERATE ATTACKS" badge={genMode.toUpperCase()}>
              <div className="flex gap-1 mb-3">
                <button
                  onClick={() => setGenMode("random")}
                  className={`mil-btn mil-btn-sm flex-1 ${genMode === "random" ? "mil-btn-primary" : ""}`}
                >
                  RANDOM
                </button>
                <button
                  onClick={() => setGenMode("ai")}
                  className={`mil-btn mil-btn-sm flex-1 ${genMode === "ai" ? "mil-btn-primary" : ""}`}
                >
                  AI
                </button>
              </div>

              {genMode === "random" ? (
                <div className="space-y-2">
                  <p className="text-[11px] text-dim">
                    Create a deterministic batch of varied attack plans respecting resource limits.
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <div className="mil-label mb-1">Count</div>
                      <input
                        type="number"
                        value={randomCount}
                        onChange={(e) => setRandomCount(Number(e.target.value))}
                        min={1}
                        max={50}
                        className="mil-input"
                      />
                    </div>
                    <div>
                      <div className="mil-label mb-1">Seed</div>
                      <input
                        type="number"
                        value={randomSeed}
                        onChange={(e) => setRandomSeed(Number(e.target.value))}
                        className="mil-input"
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-[11px] text-dim">
                    Describe the attack shape you want. The LLM produces one plan.
                  </p>
                  <textarea
                    value={aiPrompt}
                    onChange={(e) => setAiPrompt(e.target.value)}
                    className="mil-textarea"
                    rows={5}
                  />
                  <p className="text-[10px] text-warn">Requires ANTHROPIC_API_KEY.</p>
                </div>
              )}

              <button
                onClick={onGenerate}
                disabled={generating}
                className="mil-btn mil-btn-primary w-full mt-3"
              >
                {generating
                  ? "◌ GENERATING..."
                  : genMode === "random"
                  ? `⚙ GENERATE ${randomCount} PLANS`
                  : "◈ GENERATE VIA CLAUDE"}
              </button>
            </Panel>

            <Panel title="② START TRAINING" badge={`${selectedPlans.size} SELECTED`}>
              <div className="space-y-3">
                <div>
                  <div className="mil-label mb-1">Defense Playbook</div>
                  <select
                    value={playbookId}
                    onChange={(e) => setPlaybookId(e.target.value)}
                    className="mil-select"
                  >
                    <option value="">[ NEW — generated via AI from doctrine ]</option>
                    {playbooks.map((p) => (
                      <option key={p.playbook_id} value={p.playbook_id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>
                {!playbookId && (
                  <div>
                    <div className="mil-label mb-1">Extra guidance (optional)</div>
                    <textarea
                      value={extraPrompt}
                      onChange={(e) => setExtraPrompt(e.target.value)}
                      className="mil-textarea"
                      rows={2}
                      placeholder="e.g., 'prioritize bomber interception'"
                    />
                  </div>
                )}
                <button
                  onClick={onStartTraining}
                  disabled={starting || selectedPlans.size === 0}
                  className="mil-btn mil-btn-primary w-full"
                >
                  {starting ? "◌ STARTING..." : `⚡ TRAIN ON ${selectedPlans.size} PLANS`}
                </button>
                <p className="text-[10px] text-dim">
                  Runs one simulation per selected attack against the playbook, analyzes each,
                  then synthesizes doctrine updates.
                </p>
              </div>
            </Panel>

            {activeJob && (
              <Panel title="CURRENT JOB" badge={activeJob.status.toUpperCase()}>
                <div className="space-y-2">
                  <div className="font-mono text-[10px] text-dim">{activeJob.job_id}</div>
                  {(() => {
                    const phase = activeJob.result_summary?.phase;
                    const phaseLabels: Record<string, string> = {
                      playbook: "Generating playbook",
                      simulating: "Running simulations",
                      analyzing: "Analyzing matches",
                      persisting: "Saving results",
                      synthesizing: "Synthesizing doctrine",
                      completed: "Completed",
                    };
                    const label =
                      activeJob.status === "completed"
                        ? "Completed"
                        : activeJob.status === "failed"
                        ? "Failed"
                        : activeJob.status === "pending"
                        ? "Queued"
                        : phase
                        ? phaseLabels[phase] ?? "Running"
                        : "Running";
                    const pct =
                      activeJob.status === "completed"
                        ? 100
                        : Math.min(
                            100,
                            Math.round(
                              (activeJob.progress_current /
                                Math.max(activeJob.progress_total, 1)) *
                                100,
                            ),
                          );
                    return (
                      <>
                        <div className="flex items-center justify-between text-xs">
                          <span>{label}</span>
                          <span className="font-mono text-dim">{pct}%</span>
                        </div>
                        <div className="h-1.5 bg-surface-1 overflow-hidden">
                          <div
                            className="h-full transition-all"
                            style={{
                              width: `${pct}%`,
                              background: "var(--accent)",
                            }}
                          />
                        </div>
                      </>
                    );
                  })()}
                  {activeJob.result_summary?.total_matches !== undefined && (
                    <>
                      <hr className="mil-divider" />
                      <MetricRow label="Matches" value={activeJob.result_summary.total_matches ?? 0} />
                      <MetricRow label="Wins" value={activeJob.result_summary.wins ?? 0} />
                      <MetricRow label="Losses" value={activeJob.result_summary.losses ?? 0} />
                      <MetricRow label="Timeouts" value={activeJob.result_summary.timeouts ?? 0} />
                      <MetricRow
                        label="Avg Fitness"
                        value={activeJob.result_summary.avg_fitness?.toFixed(1) ?? "—"}
                      />
                      <MetricRow
                        label="Doctrine Updates"
                        value={
                          (activeJob.result_summary.doctrine_updates?.additions ?? 0) +
                          (activeJob.result_summary.doctrine_updates?.reinforcements ?? 0) +
                          (activeJob.result_summary.doctrine_updates?.supersessions ?? 0)
                        }
                      />
                    </>
                  )}
                  {activeJob.error && <div className="text-xs text-danger">{activeJob.error}</div>}
                </div>
              </Panel>
            )}
          </div>

          {/* RIGHT COLUMN: Attack library + job history */}
          <div className="space-y-4">
            <Panel
              title={`ATTACK SETS (${groups.length} groups · ${plans.length} plans)`}
              actions={
                <span className="flex gap-1">
                  <button onClick={selectAll} className="mil-btn mil-btn-sm">
                    SELECT ALL
                  </button>
                  <button onClick={clearSelection} className="mil-btn mil-btn-sm">
                    CLEAR
                  </button>
                </span>
              }
            >
              <div className="max-h-[480px] overflow-y-auto space-y-2">
                {groups.length === 0 ? (
                  <p className="text-dim text-xs p-3">
                    [ no attack plans yet — use the generator on the left ]
                  </p>
                ) : (
                  groups.map((g) => {
                    const allSelected = g.plans.every((p) => selectedPlans.has(p.plan_id));
                    const someSelected =
                      g.plans.some((p) => selectedPlans.has(p.plan_id)) && !allSelected;
                    return (
                      <div key={g.key} className="mil-panel">
                        <div
                          className="flex items-center justify-between p-2 cursor-pointer hover:bg-surface-1"
                          onClick={() => toggleGroup(g)}
                          style={{
                            background: selectedGroup === g.key ? "var(--surface-2)" : undefined,
                          }}
                        >
                          <div className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={allSelected}
                              ref={(el) => {
                                if (el) el.indeterminate = someSelected;
                              }}
                              readOnly
                              className="accent-green-400"
                            />
                            <div>
                              <div className="mil-value text-xs">{g.label}</div>
                              <div className="text-[10px] text-dim">
                                {g.plans.length} plans · {g.source}
                              </div>
                            </div>
                          </div>
                          <span className="mil-badge mil-badge-dim">
                            {g.source.substring(0, 3).toUpperCase()}
                          </span>
                        </div>
                        <div className="border-t border-mil">
                          {g.plans.map((p) => (
                            <div
                              key={p.plan_id}
                              className="flex items-center gap-2 px-3 py-1 text-[11px] hover:bg-surface-1 cursor-pointer"
                              onClick={() => togglePlan(p.plan_id)}
                            >
                              <input
                                type="checkbox"
                                checked={selectedPlans.has(p.plan_id)}
                                readOnly
                                className="accent-green-400"
                              />
                              <div className="flex-1">
                                <div className="mil-value">{p.name}</div>
                                <div className="text-[10px] text-dim font-mono">
                                  {p.actions.length} actions · {p.pattern_id?.substring(0, 12)}
                                </div>
                              </div>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onDeletePlan(p.plan_id);
                                }}
                                className="mil-btn mil-btn-sm mil-btn-danger"
                              >
                                DEL
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </Panel>

            <Panel title={`JOB HISTORY (${jobs.length})`}>
              <div className="max-h-[260px] overflow-y-auto">
                <table className="mil-table">
                  <thead>
                    <tr>
                      <th>JOB</th>
                      <th>STATUS</th>
                      <th>PROGRESS</th>
                      <th>STARTED</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map((j) => (
                      <tr key={j.job_id}>
                        <td className="font-mono text-[10px]">{j.job_id}</td>
                        <td>
                          <span
                            className={`mil-badge ${
                              j.status === "completed"
                                ? "mil-badge-win"
                                : j.status === "failed"
                                ? "mil-badge-loss"
                                : j.status === "running"
                                ? "mil-badge-running"
                                : "mil-badge-dim"
                            }`}
                          >
                            {j.status.toUpperCase()}
                          </span>
                        </td>
                        <td className="font-mono">
                          {j.progress_current}/{j.progress_total}
                        </td>
                        <td className="text-[10px] text-dim">
                          {j.started_at?.substring(11, 19)}
                        </td>
                        <td>
                          <button
                            onClick={() => setActiveJobId(j.job_id)}
                            className="mil-btn mil-btn-sm"
                          >
                            VIEW
                          </button>
                        </td>
                      </tr>
                    ))}
                    {jobs.length === 0 && (
                      <tr>
                        <td colSpan={5} className="text-center text-dim py-4">
                          [ no jobs yet ]
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </Panel>
          </div>
        </div>
      </main>
    </div>
  );
}
