"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/mil/Header";
import { Panel, MetricRow } from "@/components/mil/Panel";
import {
  activateSettings,
  createSettingsFromScenario,
  deleteSettings,
  getActiveSettings,
  listSettings,
  resetAllData,
  type Settings,
  type SettingsDetail,
} from "@/lib/api";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [active, setActive] = useState<SettingsDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [newName, setNewName] = useState("Boreal Passage — Custom");

  const refresh = async () => {
    try {
      const [list, act] = await Promise.all([
        listSettings(),
        getActiveSettings().catch(() => null),
      ]);
      setSettings(list.settings);
      setActiveId(list.active_id);
      setActive(act);
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => { refresh(); }, []);

  const handleCreate = async () => {
    setLoading(true);
    setError(null);
    try {
      await createSettingsFromScenario({ name: newName });
      await refresh();
    } catch (e) { setError(String(e)); } finally { setLoading(false); }
  };

  const handleActivate = async (id: string) => {
    setError(null);
    try {
      await activateSettings(id);
      await refresh();
    } catch (e) { setError(String(e)); }
  };

  const handleResetAll = async () => {
    const confirmed = confirm(
      "⚠ DANGER — IRREVERSIBLE ACTION\n\n" +
      "This will permanently delete ALL data in the database:\n" +
      "  • All settings\n" +
      "  • All doctrine entries\n" +
      "  • All attack plans & patterns\n" +
      "  • All defense playbooks\n" +
      "  • All match results & training jobs\n\n" +
      "There is no undo. Are you absolutely sure?"
    );
    if (!confirmed) return;
    setResetting(true);
    setError(null);
    try {
      await resetAllData();
      await refresh();
    } catch (e) { setError(String(e)); } finally { setResetting(false); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete these settings? (Associated match results will remain but orphaned.)")) return;
    try {
      await deleteSettings(id);
      await refresh();
    } catch (e) { setError(String(e)); }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1 p-6 max-w-[1600px] mx-auto w-full">
        <div className="mb-6">
          <h1 className="mil-heading text-2xl mb-1">⚙ SETTINGS</h1>
          <p className="text-dim text-sm tracking-wider">SCENARIO CONFIG // TRAINING SCOPE</p>
        </div>

        {error && (
          <div className="mil-panel mb-4 p-3 border-red-900/50">
            <span className="text-danger text-xs">⚠ {error}</span>
          </div>
        )}

        <div className="grid grid-cols-[1fr_380px] gap-4">
          <Panel title={`STORED SETTINGS (${settings.length})`} badge={activeId ? "ACTIVE SET" : "NONE ACTIVE"}>
            <table className="mil-table">
              <thead>
                <tr>
                  <th>NAME</th>
                  <th>ID</th>
                  <th>TICK MIN</th>
                  <th>MAX TICKS</th>
                  <th>CREATED</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {settings.map((s) => (
                  <tr key={s.settings_id}
                      style={{ background: s.settings_id === activeId ? "var(--surface-2)" : undefined }}>
                    <td className="mil-value">{s.name}</td>
                    <td className="font-mono text-[10px] text-dim">{s.settings_id.substring(0, 16)}…</td>
                    <td className="font-mono">{s.tick_minutes}</td>
                    <td className="font-mono">{s.max_ticks}</td>
                    <td className="text-[10px] text-dim">{s.created_at?.substring(0, 10)}</td>
                    <td>
                      <div className="flex gap-1">
                        {s.settings_id !== activeId && (
                          <button onClick={() => handleActivate(s.settings_id)}
                                  className="mil-btn mil-btn-sm">ACTIVATE</button>
                        )}
                        <button onClick={() => handleDelete(s.settings_id)}
                                className="mil-btn mil-btn-sm mil-btn-danger">DEL</button>
                      </div>
                    </td>
                  </tr>
                ))}
                {settings.length === 0 && (
                  <tr><td colSpan={6} className="text-center text-dim py-6">[ NO SETTINGS ]</td></tr>
                )}
              </tbody>
            </table>

            <hr className="mil-divider" />

            <div className="flex items-center gap-2">
              <input type="text" value={newName} onChange={(e) => setNewName(e.target.value)}
                     className="mil-input flex-1" placeholder="Name for new settings" />
              <button onClick={handleCreate} disabled={loading}
                      className="mil-btn mil-btn-primary">
                {loading ? "◌ LOADING" : "+ FROM SCENARIO"}
              </button>
            </div>
            <p className="text-[10px] text-dim mt-2">
              Loads scenario/boreal_passage.json. Content-addressable: same config reuses ID.
            </p>
          </Panel>

          <Panel title="ACTIVE DETAILS">
            {active ? (
              <div className="space-y-3">
                <div>
                  <div className="mil-label">Name</div>
                  <div className="text-sm mil-value">{active.name}</div>
                </div>
                <MetricRow label="Tick minutes" value={active.tick_minutes} />
                <MetricRow label="Max ticks" value={active.max_ticks} />
                <hr className="mil-divider" />
                <div>
                  <div className="mil-label mb-1">Defender Resources</div>
                  <div className="text-[11px] text-dim font-mono">
                    {Object.entries(active.defender_resources).map(([base, types]) => (
                      <div key={base}>
                        {base}: {Object.entries(types).map(([t, c]) => `${c} ${t}`).join(", ")}
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="mil-label mb-1">Attacker Resources</div>
                  <div className="text-[11px] text-dim font-mono">
                    {Object.entries(active.attacker_resources).map(([base, types]) => (
                      <div key={base}>
                        {base}: {Object.entries(types).map(([t, c]) => `${c} ${t}`).join(", ")}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-dim text-xs">No active settings. Create one from scenario.</p>
            )}
          </Panel>
        </div>

        <div className="mt-8 border border-red-900/60 rounded p-5"
             style={{ background: "rgba(180,20,20,0.06)" }}>
          <div className="flex items-start justify-between gap-6">
            <div>
              <div className="text-red-400 font-mono font-bold tracking-widest text-sm mb-1">
                ⚠ DANGER ZONE
              </div>
              <div className="text-xs text-dim max-w-lg">
                Permanently wipes every record from the database — settings, doctrine, attack plans,
                defense playbooks, match results, and training jobs. This action cannot be undone.
              </div>
            </div>
            <button
              onClick={handleResetAll}
              disabled={resetting}
              className="shrink-0 font-mono font-bold tracking-widest text-xs px-5 py-2 rounded border"
              style={{
                background: resetting ? "rgba(180,20,20,0.2)" : "rgba(180,20,20,0.15)",
                borderColor: "rgba(200,30,30,0.7)",
                color: resetting ? "#888" : "#f87171",
                cursor: resetting ? "not-allowed" : "pointer",
              }}
            >
              {resetting ? "◌ RESETTING..." : "✕ RESET ALL DATA"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
