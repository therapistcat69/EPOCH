"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ml } from "@/lib/ml-api";

/** Compact, honest model-provenance line shown on the home and video pages. */
export default function ModelProvenance() {
  const q = useQuery({ queryKey: ["ml-status"], queryFn: ml.status, refetchInterval: (x) => (x.state.data?.state === "loading" ? 4000 : false) });
  const s = q.data;
  if (!s) return null;
  if (!s.model_available) return <p className="text-xs text-neutral-500">RetainAI model: {s.state === "loading" ? "loading…" : "not available"}</p>;
  const real = s.real_samples ?? 0;
  const syn = s.synthetic_samples ?? 0;
  return (
    <p className="text-xs text-neutral-500">
      RetainAI model <b>{s.model_version}</b> · trained with {syn + real} videos ({syn} synthetic + {real} real)
      {s.last_trained ? ` · ${s.last_trained.slice(0, 10)}` : ""} · {s.real_validation_available ? "real holdout validation available" : "no real-data validation yet"} ·{" "}
      <Link href="/models" className="underline">details</Link>
    </p>
  );
}
