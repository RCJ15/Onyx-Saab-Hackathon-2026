"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/mil/Header";
import { Panel } from "@/components/mil/Panel";
import {
  deletePlaybook,
  getKnowledgeBundle,
  type AttackPattern,
  type DefensePlaybook,
  type DoctrineEntry,
  type KnowledgeBundle,
} from "@/lib/api";
import { getCached, invalidate, setCached } from "@/lib/cache";

const CACHE_TTL = 5 * 60_000;   // 5 minutes
const BUNDLE_KEY = "kb:bundle";

function applyBundle(
  b: KnowledgeBundle,
  setters: {
    setCounts: (v: Record<string, number>) => void;
    setDoctrine: (v: DoctrineEntry[]) => void;
    setPatterns: (v: AttackPattern[]) => void;
    setPlaybooks: (v: DefensePlaybook[]) => void;
    setMatches: (v: Array<Record<string, unknown>>) => void;
  },
) {
  setters.setCounts(b.counts);
  setters.setDoctrine(b.doctrine);
  setters.setPatterns(b.patterns);
  setters.setPlaybooks(b.playbooks);
  setters.setMatches(b.matches);
}

export default function KnowledgePage() {
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [doctrine, setDoctrine] = useState<DoctrineEntry[]>([]);
  const [patterns, setPatterns] = useState<AttackPattern[]>([]);
  const [playbooks, setPlaybooks] = useState<DefensePlaybook[]>([]);
  const [selectedPlaybook, setSelectedPlaybook] = useState<DefensePlaybook | null>(null);
  const [matches, setMatches] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"doctrine" | "patterns" | "playbooks" | "matches">("doctrine");

  const setters = { setCounts, setDoctrine, setPatterns, setPlaybooks, setMatches };

  const revalidate = () =>
    getKnowledgeBundle(50)
      .then((b) => {
        setCached(BUNDLE_KEY, b);
        applyBundle(b, setters);
      })
      .catch((e) => setError(String(e)));

  const loadAll = (force = false) => {
    if (force) invalidate("kb");
    return revalidate();
  };

  useEffect(() => {
    // Synchronously paint from localStorage cache (no network), then revalidate.
    const hit = getCached<KnowledgeBundle>(BUNDLE_KEY, CACHE_TTL);
    if (hit) applyBundle(hit, setters);
    revalidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onRefresh = () => loadAll(true);

  const onDeletePlaybook = async (id: string) => {
    if (!confirm("Delete this playbook?")) return;
    try {
      await deletePlaybook(id);
      if (selectedPlaybook?.playbook_id === id) setSelectedPlaybook(null);
      await loadAll(true);
    } catch (e) { setError(String(e)); }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 p-6 max-w-[1800px] mx-auto w-full">
        <div className="mb-6 flex justify-between items-end">
          <div>
            <h1 className="mil-heading text-2xl mb-1">⌧ KNOWLEDGE BASE</h1>
            <p className="text-dim text-sm tracking-wider">
              DOCTRINE · PATTERNS · PLAYBOOKS · MATCHES
            </p>
          </div>
          <button onClick={onRefresh} className="mil-btn mil-btn-sm">↻ REFRESH</button>
        </div>

        {error && (
          <div className="mil-panel mb-4 p-3 border-red-900/50">
            <span className="text-danger text-xs">⚠ {error}</span>
          </div>
        )}

        <div className="grid grid-cols-4 gap-4 mb-6">
          <Panel title="DOCTRINE">
            <div className="text-3xl mil-value-accent font-bold">{counts.doctrine_entries ?? 0}</div>
            <div className="text-dim text-xs">active principles</div>
          </Panel>
          <Panel title="PATTERNS">
            <div className="text-3xl mil-value-accent font-bold">{counts.attack_patterns ?? 0}</div>
            <div className="text-dim text-xs">unique attack shapes</div>
          </Panel>
          <Panel title="PLAYBOOKS">
            <div className="text-3xl mil-value-accent font-bold">{counts.defense_playbooks ?? 0}</div>
            <div className="text-dim text-xs">in library</div>
          </Panel>
          <Panel title="MATCHES">
            <div className="text-3xl mil-value-accent font-bold">{counts.match_results ?? 0}</div>
            <div className="text-dim text-xs">simulation outcomes</div>
          </Panel>
        </div>

        <div className="mil-nav mb-4">
          {([
            ["doctrine", "DOCTRINE"],
            ["patterns", "PATTERNS"],
            ["playbooks", "PLAYBOOKS"],
            ["matches", "MATCHES"],
          ] as const).map(([k, label]) => (
            <button
              key={k}
              onClick={() => setTab(k)}
              className="mil-nav-item"
              data-state={tab === k ? "active" : "inactive"}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "doctrine" && (
          <Panel title={`DOCTRINE ENTRIES (${doctrine.length})`}>
            <div className="space-y-2">
              {doctrine.map((d) => (
                <div key={d.entry_id} className="mil-panel p-3">
                  <div className="flex justify-between items-start mb-1">
                    <span className="mil-badge mil-badge-dim">{d.category}</span>
                    <span className="text-[10px] text-dim font-mono">
                      v{d.version} · conf {(d.confidence_score * 100).toFixed(0)}%
                      {d.human_edited && " · EDITED"}
                    </span>
                  </div>
                  <div className="text-sm mil-value mb-1">{d.principle_text}</div>
                  {Object.keys(d.trigger_conditions || {}).length > 0 && (
                    <div className="text-[10px] text-dim font-mono mt-1">
                      when: {JSON.stringify(d.trigger_conditions)}
                    </div>
                  )}
                  <div className="text-[10px] text-muted mt-1">
                    supported by {d.supporting_match_ids.length} match(es)
                  </div>
                </div>
              ))}
              {doctrine.length === 0 && (
                <p className="text-dim text-xs">
                  [ doctrine is empty — run training to populate ]
                </p>
              )}
            </div>
          </Panel>
        )}

        {tab === "patterns" && (
          <Panel title={`ATTACK PATTERNS (${patterns.length})`}>
            <table className="mil-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>DESCRIPTION</th>
                  <th>WAVES</th>
                  <th>PLANS</th>
                  <th>MATCHES</th>
                  <th>BEST FITNESS</th>
                  <th>TAGS</th>
                </tr>
              </thead>
              <tbody>
                {patterns.map((p) => (
                  <tr key={p.pattern_id}>
                    <td className="font-mono text-[10px]">{p.pattern_id.substring(0, 12)}</td>
                    <td>{p.canonical_description}</td>
                    <td className="font-mono">{p.wave_count}</td>
                    <td className="font-mono">{p.total_plans_count}</td>
                    <td className="font-mono">{p.total_matches_count}</td>
                    <td className="font-mono text-accent">
                      {p.best_fitness_score !== null ? p.best_fitness_score.toFixed(1) : "—"}
                    </td>
                    <td>
                      <div className="flex gap-1 flex-wrap">
                        {p.feature_tags.slice(0, 3).map((t, i) => (
                          <span key={i} className="text-[9px] text-dim">{t}</span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
                {patterns.length === 0 && (
                  <tr><td colSpan={7} className="text-center text-dim py-6">[ empty ]</td></tr>
                )}
              </tbody>
            </table>
          </Panel>
        )}

        {tab === "playbooks" && (
          <div className="grid grid-cols-[1fr_440px] gap-4">
            <Panel title={`PLAYBOOKS (${playbooks.length})`}>
              <div className="max-h-[600px] overflow-y-auto">
                <table className="mil-table">
                  <thead>
                    <tr>
                      <th>NAME</th>
                      <th>SOURCE</th>
                      <th>ORDERS</th>
                      <th>TRIGGERS</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {playbooks.map((p) => (
                      <tr key={p.playbook_id}
                          onClick={() => setSelectedPlaybook(p)}
                          style={{
                            cursor: "pointer",
                            background:
                              selectedPlaybook?.playbook_id === p.playbook_id
                                ? "var(--surface-2)"
                                : undefined,
                          }}>
                        <td>
                          <div className="mil-value text-xs">{p.name}</div>
                          <div className="text-[10px] text-dim">{p.playbook_id}</div>
                        </td>
                        <td>
                          <span className={`mil-badge ${
                            p.source === "custom" ? "mil-badge-win" :
                            p.source === "ai_generated" ? "mil-badge-running" : "mil-badge-dim"
                          }`}>
                            {p.source.substring(0, 4).toUpperCase()}
                          </span>
                        </td>
                        <td className="font-mono">{p.standing_orders.length}</td>
                        <td className="font-mono">{p.triggers.length}</td>
                        <td>
                          <button onClick={(e) => { e.stopPropagation(); onDeletePlaybook(p.playbook_id); }}
                                  className="mil-btn mil-btn-sm mil-btn-danger">DEL</button>
                        </td>
                      </tr>
                    ))}
                    {playbooks.length === 0 && (
                      <tr><td colSpan={5} className="text-center text-dim py-6">
                        [ empty — start a Training job to generate one ]
                      </td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </Panel>

            <Panel title="DETAIL">
              {selectedPlaybook ? (
                <div className="space-y-3">
                  <div>
                    <div className="mil-label">Name</div>
                    <div className="text-sm mil-value">{selectedPlaybook.name}</div>
                  </div>
                  <div>
                    <div className="mil-label">Description</div>
                    <div className="text-xs">{selectedPlaybook.description}</div>
                  </div>
                  {selectedPlaybook.doctrine_notes && (
                    <div>
                      <div className="mil-label">Doctrine Notes</div>
                      <div className="text-xs text-dim">{selectedPlaybook.doctrine_notes}</div>
                    </div>
                  )}
                  <hr className="mil-divider" />
                  <div>
                    <div className="mil-label mb-2">STANDING ORDERS ({selectedPlaybook.standing_orders.length})</div>
                    <div className="space-y-1 max-h-[180px] overflow-y-auto">
                      {selectedPlaybook.standing_orders.map((o: Record<string, unknown>, i: number) => (
                        <div key={i} className="mil-panel p-2 text-[11px]">
                          <div className="flex justify-between">
                            <span className="text-accent">{String(o.name)}</span>
                            <span className="mil-badge mil-badge-dim">{String(o.type)}</span>
                          </div>
                          <div className="text-dim mt-1">
                            {String(o.count)}× {String(o.aircraft_type)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="mil-label mb-2">TRIGGERS ({selectedPlaybook.triggers.length})</div>
                    <div className="space-y-1 max-h-[220px] overflow-y-auto">
                      {selectedPlaybook.triggers.map((t: Record<string, unknown>, i: number) => {
                        const when = t.when as { condition?: string } | undefined;
                        const action = t.action as { type?: string } | undefined;
                        return (
                          <div key={i} className="mil-panel p-2 text-[11px]">
                            <div className="flex justify-between">
                              <span className="text-accent">{String(t.name)}</span>
                              <span className="text-[9px] text-dim">pri {String(t.priority)}</span>
                            </div>
                            <div className="text-dim mt-1 font-mono">
                              WHEN: {when?.condition}
                              <br />
                              DO: {action?.type}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-dim text-xs">Select a playbook.</p>
              )}
            </Panel>
          </div>
        )}

        {tab === "matches" && (
          <Panel title={`RECENT MATCHES (${matches.length})`}>
            <div className="max-h-[600px] overflow-y-auto">
              <table className="mil-table">
                <thead>
                  <tr>
                    <th>MATCH ID</th>
                    <th>ATTACK</th>
                    <th>PLAYBOOK</th>
                    <th>OUTCOME</th>
                    <th>FITNESS</th>
                    <th>CASUALTIES</th>
                    <th>CAPITAL</th>
                    <th>TIME</th>
                  </tr>
                </thead>
                <tbody>
                  {matches.map((m) => (
                    <tr key={m.match_id as string}>
                      <td className="font-mono text-[10px]">{String(m.match_id).substring(0, 12)}</td>
                      <td className="font-mono text-[10px]">{String(m.attack_plan_id).substring(0, 12)}</td>
                      <td className="font-mono text-[10px]">{String(m.defense_playbook_id).substring(0, 12)}</td>
                      <td>
                        <span className={`mil-badge ${
                          m.outcome === "WIN" ? "mil-badge-win" :
                          m.outcome === "LOSS" ? "mil-badge-loss" : "mil-badge-timeout"
                        }`}>{m.outcome as string}</span>
                      </td>
                      <td className="font-mono mil-value-accent">{(m.fitness_score as number).toFixed(1)}</td>
                      <td className="font-mono">{(m.total_civilian_casualties as number).toLocaleString()}</td>
                      <td>{m.capital_survived ? "✓" : "✗"}</td>
                      <td className="text-[10px] text-dim">
                        {String(m.created_at).substring(11, 19)}
                      </td>
                    </tr>
                  ))}
                  {matches.length === 0 && (
                    <tr><td colSpan={8} className="text-center text-dim py-6">[ no matches yet ]</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </Panel>
        )}
      </main>
    </div>
  );
}
