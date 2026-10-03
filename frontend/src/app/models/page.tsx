"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Card, ErrorBox, Loading, Stat } from "@/components/dashboard/ui";
import { ml } from "@/lib/ml-api";

const f = (v: number | null | undefined, d = 2) => (v == null ? "N/A" : v.toFixed(d));
const BADGE: Record<string, string> = { production: "bg-green-500/20 text-green-600", candidate: "bg-blue-500/20 text-blue-500", rejected: "bg-red-500/20 text-red-500", archived: "bg-neutral-500/20 text-neutral-500" };

/** Model status / registry / retraining (development & admin). Retrain/promote need ADMIN_TOKEN, or a local backend. */
export default function ModelsPage() {
  const qc = useQueryClient();
  const [token, setToken] = useState("");
  const status = useQuery({ queryKey: ["ml-status"], queryFn: ml.status });
  const reg = useQuery({ queryKey: ["ml-models"], queryFn: ml.models, refetchInterval: (q) => (q.state.data?.training_runs.some((r) => r.status === "running") ? 5000 : false) });
  const metrics = useQuery({ queryKey: ["ml-metrics"], queryFn: ml.metrics });
  const done = () => { qc.invalidateQueries({ queryKey: ["ml-models"] }); qc.invalidateQueries({ queryKey: ["ml-status"] }); };
  const retrain = useMutation({ mutationFn: () => ml.retrain(token), onSuccess: done });
  const promote = useMutation({ mutationFn: (v: string) => ml.promote(v, token), onSuccess: done });
  const s = status.data, m = metrics.data;

  return (
    <main className="mx-auto w-full max-w-6xl space-y-4 px-4 py-6">
      <Link href="/" className="flex items-center gap-1 text-sm text-neutral-500 hover:underline"><ArrowLeft className="size-4" /> Home</Link>
      <h1 className="text-3xl font-bold">Model status</h1>

      <Card title="Production model">
        {status.isLoading && <Loading />}
        {s && (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Model" value={s.model_available ? `${s.model_name} ${s.model_version}` : s.state} sub={s.message} />
            <Stat label="Training data" value={`${(s.synthetic_samples ?? 0) + (s.real_samples ?? 0)} videos`} sub={`${s.synthetic_samples ?? 0} synthetic · ${s.real_samples ?? 0} real`} />
            <Stat label="Last trained" value={s.last_trained?.slice(0, 10) ?? "N/A"} sub={`schema ${s.feature_schema_version ?? "N/A"} · ${s.dataset_version ?? ""}`} />
            <Stat label="Real validation" value={s.real_validation_available ? "Real holdout available" : "Not available"} sub={`trained on: ${s.trained_on ?? "N/A"}`} />
          </div>
        )}
        {s?.trained_on?.includes("synthetic") && <p className="mt-3 text-xs font-bold tracking-widest text-yellow-600">DEVELOPMENT MODEL · TRAINED WITH SYNTHETIC BOOTSTRAP DATA · NOT VALIDATED ON REAL YOUTUBE RETENTION</p>}
      </Card>

      <Card title="Monitoring">
        {m && (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Predictions stored" value={String(m.prediction_count)} />
            <Stat label="Real labelled videos" value={String(m.real_labeled_videos)} sub={`retrain after ${reg.data?.retrain_after_real_labels ?? 20}`} />
            <Stat label="Recent real-data MAE" value={f(m.average_recent_error_mae)} sub={`${m.recent_error_samples} videos`} />
            <Stat label="Drift warning" value={m.drift_warning == null ? "Not assessed" : m.drift_warning ? "Yes" : "No"} sub={m.drift_note} />
          </div>
        )}
      </Card>

      <Card title="Model versions" right={
        <div className="flex items-center gap-2">
          <input value={token} onChange={(e) => setToken(e.target.value)} type="password" placeholder="Admin token (if configured)" className="rounded-lg border border-neutral-400/40 bg-transparent px-2 py-1 text-sm" />
          <button onClick={() => retrain.mutate()} disabled={retrain.isPending} className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60">Retrain candidate</button>
        </div>
      }>
        {reg.isLoading && <Loading />}
        {reg.error && <ErrorBox error={reg.error} />}
        {(retrain.error || promote.error) && <ErrorBox error={retrain.error ?? promote.error} />}
        {retrain.data && <p className="mb-2 text-sm text-neutral-500">Training {retrain.data.candidate_version} started. {retrain.data.note}</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-neutral-500"><tr><th className="py-1">Version</th><th>Status</th><th>Samples (syn/real)</th><th>MAE</th><th>RMSE</th><th>R²</th><th>Pearson</th><th>Spearman</th><th /></tr></thead>
            <tbody>
              {reg.data?.models.map((r) => (
                <tr key={r.id} className="border-t border-neutral-400/20">
                  <td className="py-1.5 font-medium">{r.model_name} {r.model_version}</td>
                  <td><span className={`rounded px-1.5 py-0.5 text-xs ${BADGE[r.status]}`}>{r.status}</span></td>
                  <td>{r.synthetic_samples} / {r.real_samples}</td><td>{f(r.mae)}</td><td>{f(r.rmse)}</td><td>{f(r.r2, 3)}</td><td>{f(r.pearson, 3)}</td><td>{f(r.spearman, 3)}</td>
                  <td>{(r.status === "archived" || r.status === "candidate") && <button onClick={() => promote.mutate(r.model_version)} className="text-xs underline">{r.status === "archived" ? "Roll back" : "Promote"}</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-neutral-500">Metrics are measured on the protected synthetic test split (never trained on). A candidate is promoted only if MAE is not worse, correlation and risk recall are maintained.</p>
      </Card>

      <Card title="Training runs">
        {reg.data?.training_runs.length === 0 && <p className="text-sm text-neutral-500">No retraining runs yet.</p>}
        <ul className="space-y-2 text-sm">
          {reg.data?.training_runs.map((r) => (
            <li key={r.id}><b>{r.candidate_version}</b> · {r.reason} · {r.status}{r.started_at ? ` · ${r.started_at.slice(0, 16).replace("T", " ")}` : ""}
              {r.decision && <p className="text-xs text-neutral-500">{r.decision}</p>}</li>
          ))}
        </ul>
      </Card>
    </main>
  );
}
