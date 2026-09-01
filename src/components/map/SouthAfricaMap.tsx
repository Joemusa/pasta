"use client";

import { useState } from "react";
import type { ProvinceId, ProvinceIntel, Severity } from "@/lib/types";
import { SeverityDot } from "@/components/ui/severity";
import { cn } from "@/lib/utils";

const PATHS: { id: ProvinceId; d: string }[] = [
  {
    id: "limpopo",
    d: "M210 18 L310 22 L355 70 L340 118 L270 125 L200 108 L188 70 Z",
  },
  {
    id: "mpumalanga",
    d: "M310 22 L368 38 L378 110 L340 118 L355 70 Z",
  },
  {
    id: "gauteng",
    d: "M248 118 L292 114 L300 142 L262 150 L240 138 Z",
  },
  {
    id: "north-west",
    d: "M130 95 L200 108 L240 138 L230 175 L150 180 L118 140 Z",
  },
  {
    id: "free-state",
    d: "M150 180 L230 175 L262 150 L300 155 L305 205 L210 230 L148 215 Z",
  },
  {
    id: "kwazulu-natal",
    d: "M300 142 L378 110 L395 150 L360 230 L305 205 L300 155 Z",
  },
  {
    id: "northern-cape",
    d: "M40 120 L118 140 L150 180 L148 215 L120 280 L55 300 L28 210 Z",
  },
  {
    id: "eastern-cape",
    d: "M148 215 L210 230 L305 205 L360 230 L300 310 L180 305 L120 280 Z",
  },
  {
    id: "western-cape",
    d: "M28 210 L55 300 L120 280 L180 305 L150 345 L70 355 L22 280 Z",
  },
];

function worst(p: ProvinceIntel): Severity {
  const order: Record<Severity, number> = { critical: 4, high: 3, medium: 2, low: 1 };
  return p.signals.reduce<Severity>((best, s) => (order[s.severity] > order[best] ? s.severity : best), "low");
}

export function SouthAfricaMap({ provinces }: { provinces: ProvinceIntel[] }) {
  const [selected, setSelected] = useState<ProvinceId>("gauteng");
  const byId = Object.fromEntries(provinces.map((p) => [p.id, p]));
  const current = byId[selected];

  return (
    <div className="grid gap-6 border border-rule bg-white p-4 lg:grid-cols-[1.2fr_1fr]">
      <svg viewBox="0 0 420 380" className="h-auto w-full max-h-[420px]" role="img" aria-label="South Africa provinces">
        {PATHS.map((p) => {
          const intel = byId[p.id];
          const level = intel ? worst(intel) : "low";
          const fill =
            level === "critical"
              ? "#f4d7d4"
              : level === "high"
                ? "#f6ddd0"
                : level === "medium"
                  ? "#f3e6c8"
                  : "#dde8df";
          return (
            <path
              key={p.id}
              d={p.d}
              fill={selected === p.id ? "#1e4f48" : fill}
              stroke="#10161c"
              strokeWidth={1}
              className="cursor-pointer"
              onClick={() => setSelected(p.id)}
            />
          );
        })}
      </svg>
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-muted">Province</p>
        <h3 className="font-serif text-2xl">{current?.name}</h3>
        <p className="mt-2 text-sm leading-relaxed text-muted">{current?.summary}</p>
        <ul className="mt-4 space-y-2">
          {current?.signals.map((s) => (
            <li key={s.label} className="flex items-center justify-between border-b border-rule py-2 text-sm">
              <span>{s.label}</span>
              <SeverityDot level={s.severity} />
            </li>
          ))}
        </ul>
        <div className="mt-4 flex flex-wrap gap-3 text-xs text-muted">
          <span className={cn("inline-flex items-center gap-1")}><i className="h-2 w-2 bg-critical/40" /> Critical / high</span>
          <span className="inline-flex items-center gap-1">Medium</span>
          <span>Low / quiet</span>
        </div>
      </div>
    </div>
  );
}
