"use client";

import { clock } from "@/lib/format";
import type { DropOff } from "@/lib/intel-api";

export default function ObservedDropoffCard({ drops, onSelect }: { drops: DropOff[]; onSelect: (seconds: number) => void }) {
  if (!drops.length) return <p className="text-sm text-neutral-500">Data unavailable — no observed audience declines to show.</p>;
  return (
    <div className="space-y-2">
      <p className="text-sm text-neutral-500">Largest observed declines in the audience watch ratio, linked to what was being said. These are observations, not predictions.</p>
      {drops.map((d, i) => (
        <div key={i} className="rounded-lg border border-neutral-400/30 p-3 text-sm">
          <button className="font-semibold underline" onClick={() => d.from_seconds != null && onSelect(d.from_seconds)}>
            {d.from_seconds != null ? `${clock(d.from_seconds)}–${clock(d.to_seconds)}` : `${(d.from_ratio * 100).toFixed(0)}%–${(d.to_ratio * 100).toFixed(0)}% of the video`}
          </button>{" "}
          — audience watch ratio declined by {(d.drop * 100).toFixed(1)} percentage points.
          {d.transcript.length > 0 ? (
            <div className="mt-1 text-neutral-500">At this timestamp the transcript shows: {d.transcript.map((t, j) => <span key={j}>“{t.text}” </span>)}</div>
          ) : <div className="mt-1 text-neutral-500">No transcript for this span.</div>}
        </div>
      ))}
    </div>
  );
}
