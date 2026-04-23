"use client";

import { useRef, useEffect, useCallback, useMemo, useState } from "react";
import type { Replay, ReplayTick } from "@/lib/api";

const THEATER_W = 1667;
const THEATER_H = 1300;

type TerrainFeature = {
  id: string;
  name: string;
  side: string;
  type: "mainland" | "island" | "peninsula";
  coordinates: [number, number][];
};

type MapData = {
  locations: Array<{
    id: string;
    name: string;
    side: string;
    subtype: string;
    x_km: number;
    y_km: number;
  }>;
  terrain: TerrainFeature[];
};

type Aircraft = {
  id: string;
  type: string;
  side: string;
  position: [number, number];
  state: string;
  fuel: number;
  ammo: number;
  damage_level?: string;
};

type Location = {
  id: string;
  name: string;
  side: string;
  position: [number, number];
  archetype: string;
  is_destroyed?: boolean;
  is_launch_disabled?: boolean;
  casualties?: number;
};

const sx = (x: number, w: number) => (x / THEATER_W) * w;
const sy = (y: number, h: number) => (y / THEATER_H) * h;

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

export function TacticalMap({
  replay,
  tickFloat,
}: {
  replay: Replay | null;
  tickFloat: number;   // fractional tick for smooth interpolation
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [mapData, setMapData] = useState<MapData | null>(null);

  // Load map data from JSON
  useEffect(() => {
    fetch("/boreal_passage_map.json")
      .then((res) => res.json())
      .then((data: MapData) => setMapData(data))
      .catch((err) => console.error("Failed to load map data:", err));
  }, []);

  // Build an aircraft-position index by id → [tick, position] pairs for fast lookup
  const aircraftTimeline = useMemo(() => {
    if (!replay) return new Map<string, Array<{ tick: number; pos: [number, number]; state: string; type: string; side: string; fuel: number; damage_level: string }>>();
    const map = new Map<string, Array<{ tick: number; pos: [number, number]; state: string; type: string; side: string; fuel: number; damage_level: string }>>();
    replay.ticks.forEach((t, i) => {
      for (const a of (t.aircraft as unknown as Aircraft[])) {
        let arr = map.get(a.id);
        if (!arr) {
          arr = [];
          map.set(a.id, arr);
        }
        arr.push({
          tick: i,
          pos: a.position,
          state: a.state,
          type: a.type,
          side: a.side,
          fuel: a.fuel,
          damage_level: a.damage_level ?? "none",
        });
      }
    });
    return map;
  }, [replay]);

  const draw = useCallback(
    (ctx: CanvasRenderingContext2D, w: number, h: number) => {
      // ===== Background =====
      ctx.fillStyle = "#05100a";
      ctx.fillRect(0, 0, w, h);

      // Grid
      ctx.strokeStyle = "rgba(74, 222, 128, 0.04)";
      ctx.lineWidth = 0.5;
      for (let x = 0; x < w; x += 40) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let y = 0; y < h; y += 40) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }

      // Terrain from map data
      if (mapData) {
        for (const terrain of mapData.terrain) {
          const isNorth = terrain.side === "north";
          const color = isNorth ? "rgba(34, 80, 50, 0.25)" : "rgba(60, 40, 25, 0.25)";
          const strokeColor = isNorth ? "rgba(74, 222, 128, 0.3)" : "rgba(200, 130, 70, 0.3)";

          ctx.fillStyle = color;
          ctx.strokeStyle = strokeColor;
          ctx.lineWidth = 1;
          ctx.beginPath();

          const [firstX, firstY] = terrain.coordinates[0];
          ctx.moveTo(sx(firstX, w), sy(firstY, h));

          for (let i = 1; i < terrain.coordinates.length; i++) {
            const [x, y] = terrain.coordinates[i];
            ctx.lineTo(sx(x, w), sy(y, h));
          }

          ctx.closePath();
          ctx.fill();
          ctx.stroke();
        }
      }

      ctx.fillStyle = "rgba(74, 222, 128, 0.08)";
      ctx.font = "bold 16px monospace";
      ctx.textAlign = "center";
      ctx.fillText("BOREAL PASSAGE", w / 2, h * 0.56);

      if (!replay) {
        ctx.fillStyle = "rgba(74, 222, 128, 0.3)";
        ctx.font = "10px monospace";
        ctx.fillText("[ NO REPLAY ]", w / 2, h / 2 + 50);
        return;
      }

      // Clamp tick
      const maxTick = replay.ticks.length - 1;
      const clampedTickFloat = Math.max(0, Math.min(maxTick, tickFloat));
      const intTick = Math.floor(clampedTickFloat);
      const subTick = clampedTickFloat - intTick;
      const tickA: ReplayTick = replay.ticks[intTick];
      const tickB: ReplayTick | undefined = replay.ticks[Math.min(maxTick, intTick + 1)];

      // ===== Locations (static per tick — use tickA) =====
      for (const loc of (tickA.locations as unknown as Location[])) {
        const [x, y] = loc.position;
        const lx = sx(x, w);
        const ly = sy(y, h);
        const isNorth = loc.side === "north";
        const color = isNorth ? "#4ade80" : "#fb923c";
        const archetype = loc.archetype;

        if (archetype === "air_base" || archetype === "forward_base") {
          ctx.fillStyle = loc.is_destroyed ? "#666" : color;
          ctx.beginPath();
          ctx.moveTo(lx, ly - 10);
          ctx.lineTo(lx - 9, ly + 7);
          ctx.lineTo(lx + 9, ly + 7);
          ctx.closePath();
          ctx.fill();
          ctx.strokeStyle = "#000";
          ctx.lineWidth = 1;
          ctx.stroke();

          if (loc.is_launch_disabled && !loc.is_destroyed) {
            ctx.strokeStyle = "#ef4444";
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.arc(lx, ly, 14, 0, Math.PI * 2);
            ctx.stroke();
          }
        } else {
          const isCapital = archetype === "capital";
          const size = isCapital ? 11 : 8;
          let fill: string = isCapital ? "#fbbf24" : "#b8e6c6";
          if (loc.is_destroyed) fill = "#ef4444";
          ctx.fillStyle = fill;
          ctx.strokeStyle = "#000";
          ctx.fillRect(lx - size / 2, ly - size / 2, size, size);
          ctx.strokeRect(lx - size / 2, ly - size / 2, size, size);
          if (isCapital) {
            ctx.strokeStyle = fill;
            ctx.beginPath();
            ctx.arc(lx, ly, size + 4, 0, Math.PI * 2);
            ctx.stroke();
          }
        }

        ctx.fillStyle = "rgba(184, 230, 198, 0.55)";
        ctx.font = archetype === "capital" ? "bold 9px monospace" : "8px monospace";
        ctx.textAlign = "center";
        const label = loc.name.replace(" (Capital X)", "").replace(" (Capital Y)", "");
        ctx.fillText(label.toUpperCase(), lx, ly + 20);
      }

      // ===== Aircraft (interpolated) =====
      const airborneStates = new Set(["airborne", "damaged", "engaged"]);
      const acById = new Map<string, Aircraft>();
      for (const a of (tickA.aircraft as unknown as Aircraft[])) {
        acById.set(a.id, a);
      }
      const acByIdB = new Map<string, Aircraft>();
      if (tickB) {
        for (const a of (tickB.aircraft as unknown as Aircraft[])) {
          acByIdB.set(a.id, a);
        }
      }

      for (const [id, a] of acById) {
        const b = acByIdB.get(id);
        const wasAirborne = airborneStates.has(a.state);
        const willBeAirborne = b ? airborneStates.has(b.state) : wasAirborne;
        const wasDestroyed = a.state === "destroyed";
        const willBeDestroyed = b && b.state === "destroyed";

        if (wasDestroyed && !willBeDestroyed) continue;
        if (!wasAirborne && !willBeAirborne) continue;

        // Interpolated position
        const [ax, ay] = a.position;
        const [bx, by] = b ? b.position : a.position;
        const px = lerp(ax, bx, subTick);
        const py = lerp(ay, by, subTick);

        const cx = sx(px, w);
        const cy = sy(py, h);
        const color = a.side === "north" ? "#22d3ee" : "#fb923c";

        // Alpha for fade in/out
        let alpha = 1.0;
        if (!wasAirborne && willBeAirborne) alpha = subTick;
        else if (wasAirborne && !willBeAirborne) {
          alpha = 1 - subTick;
          if (willBeDestroyed) {
            // Explosion marker fading in at destination
            ctx.fillStyle = `rgba(251, 191, 36, ${subTick})`;
            ctx.beginPath();
            ctx.arc(sx(bx, w), sy(by, h), 8 * (0.5 + 0.5 * subTick), 0, Math.PI * 2);
            ctx.fill();
          }
        }

        ctx.globalAlpha = Math.max(0.15, alpha);

        // Heading indicator (line pointing to target direction)
        const dx = bx - ax;
        const dy = by - ay;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist > 0.1) {
          const ndx = dx / dist;
          const ndy = dy / dist;
          ctx.strokeStyle = color;
          ctx.lineWidth = 0.8;
          ctx.beginPath();
          ctx.moveTo(cx, cy);
          ctx.lineTo(cx + ndx * 8, cy + ndy * 8);
          ctx.stroke();
        }

        // Aircraft dot
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(cx, cy, 3.5, 0, Math.PI * 2);
        ctx.fill();

        // Ring for bomber
        if (a.type === "bomber") {
          ctx.strokeStyle = color;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.arc(cx, cy, 6, 0, Math.PI * 2);
          ctx.stroke();
        }

        // Low fuel warning
        if (a.fuel < 0.3) {
          ctx.strokeStyle = "#ef4444";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.arc(cx, cy, 8, 0, Math.PI * 2);
          ctx.stroke();
        }

        // Damaged indicator
        if (a.damage_level && a.damage_level !== "none") {
          ctx.strokeStyle = "#fbbf24";
          ctx.lineWidth = 0.8;
          ctx.beginPath();
          ctx.arc(cx, cy, 9, 0, Math.PI * 2);
          ctx.stroke();
        }
      }

      ctx.globalAlpha = 1.0;

      // ===== Engagement markers (this tick) =====
      const events = tickA.events as unknown as Array<{ type: string; position_km?: [number, number] }>;
      for (const ev of events) {
        if (ev.type === "engagement" && ev.position_km) {
          const bx = sx(ev.position_km[0], w);
          const by = sy(ev.position_km[1], h);
          ctx.strokeStyle = "#fbbf24";
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(bx, by, 12, 0, Math.PI * 2);
          ctx.stroke();
        }
      }

      // ===== HUD =====
      ctx.fillStyle = "rgba(74, 222, 128, 0.7)";
      ctx.font = "10px monospace";
      ctx.textAlign = "left";
      ctx.fillText(`T+${String(intTick).padStart(4, "0")}`, 8, 16);
      ctx.textAlign = "right";
      const airborneCount = (tickA.aircraft as unknown as Aircraft[]).filter(
        (a) => airborneStates.has(a.state),
      ).length;
      ctx.fillText(`AIRBORNE: ${airborneCount}`, w - 8, 16);
    },
    [replay, tickFloat, mapData],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.parentElement?.getBoundingClientRect();
    const w = rect?.width || 800;
    const h = (w / THEATER_W) * THEATER_H;
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    draw(ctx, w, h);
    // silence aircraftTimeline unused warning by touching it
    void aircraftTimeline;
  }, [draw, aircraftTimeline]);

  return (
    <div className="relative">
      <canvas
        ref={canvasRef}
        className="block w-full"
        style={{ aspectRatio: `${THEATER_W}/${THEATER_H}` }}
      />
    </div>
  );
}
