"use client";

import type { ReactNode } from "react";
import { Card } from "@/components/dashboard/ui";
import type { GroqState, Insight } from "@/lib/intel-api";

export function ExperimentCard({ item }: { item: Insight }) {
  return (
    <div className="rounded-lg border border-neutral-400/30 p-3 text-sm">
      {item.observation && <p><span className="font-semibold">Observation: </span>{item.observation}</p>}
      {item.interpretation && <p className="mt-1 text-neutral-500"><span className="font-semibold">Interpretation: </span>{item.interpretation}</p>}
      {item.recommendation && <p className="mt-1"><span className="font-semibold text-red-500">Experiment: </span>{item.recommendation}</p>}
    </div>
  );
}

export function ContentPatternCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-neutral-400/30 p-4">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">{title}</h3>
      {children}
    </div>
  );
}

export function List({ items, empty = "Data unavailable" }: { items: string[]; empty?: string }) {
  if (!items.length) return <p className="text-sm text-neutral-500">{empty}</p>;
  return <ul className="list-disc space-y-1 pl-5 text-sm">{items.map((t, i) => <li key={i}>{t}</li>)}</ul>;
}

/** Wraps any Groq-generated section: shows a clear "unavailable" state instead of failing the page. */
export function GroqReportCard<T>({ title, state, children }: { title: string; state: GroqState<T> | undefined; children: (r: T) => ReactNode }) {
  return (
    <Card title={title} right={<span className="rounded bg-neutral-400/20 px-2 py-0.5 text-xs">AI · explains the data above</span>}>
      {!state && <p className="text-sm text-neutral-500">Not generated.</p>}
      {state && !state.available && (
        <p className="rounded-lg border border-dashed border-neutral-400/50 p-3 text-sm text-neutral-500">
          {state.message ?? "AI report unavailable."}
        </p>
      )}
      {state?.available && state.report && children(state.report)}
    </Card>
  );
}
