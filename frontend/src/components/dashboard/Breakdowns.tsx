"use client";

import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type BreakdownRow, type Range } from "@/lib/creator-api";
import type { CreatorPalette } from "@/lib/creatorTheme";
import { clock, compact, hours, pct } from "@/lib/format";
import { Card, Empty, ErrorBox, Loading, axisStyle } from "./ui";

const TRAFFIC_NAMES: Record<string, string> = {
  YT_SEARCH: "YouTube Search",
  RELATED_VIDEO: "Suggested Videos",
  YT_OTHER_PAGE: "Browse Features",
  EXT_URL: "External",
  NO_LINK_OTHER: "Direct or Unknown",
  PLAYLIST: "Playlists",
  SUBSCRIBER: "Subscriptions",
  YT_CHANNEL: "Channel Pages",
  NOTIFICATION: "Notifications",
  END_SCREEN: "End Screens",
  SHORTS: "Shorts Feed",
};

interface BreakdownCardProps {
  kind: "traffic-sources" | "geography" | "devices";
  title: string;
  range: Range;
  name: (k: string) => string;
  firstCol: string;
  barColor?: string;
}

function BreakdownCard({ kind, title, range, name, firstCol, barColor = "#38BDF8" }: BreakdownCardProps) {
  const q = useQuery({ queryKey: [kind, range], queryFn: () => api.breakdown(kind, range) });
  const rows: BreakdownRow[] = q.data?.rows ?? [];

  return (
    <Card title={title}>
      {q.isLoading && <Loading label={`Loading ${title.toLowerCase()}…`} />}
      {q.error && <ErrorBox error={q.error} />}
      {q.data && rows.length === 0 && <Empty>No analytics returned for this date range.</Empty>}
      {rows.length > 0 && (
        <div className="space-y-5">
          <div className="h-60 pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows.map((r) => ({ ...r, label: name(r.key) }))} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                <XAxis type="number" tick={axisStyle} stroke="rgba(255,255,255,0.2)" />
                <YAxis type="category" dataKey="label" tick={axisStyle} width={120} stroke="rgba(255,255,255,0.2)" />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const r = payload[0].payload as BreakdownRow & { label: string };
                    return (
                      <div className="rounded-xl border border-white/10 bg-[#0c0d14]/95 backdrop-blur-xl p-3 text-xs text-white shadow-2xl">
                        <div className="font-semibold text-neutral-300 font-mono mb-1">{r.label}</div>
                        <div>Views: <span className="font-bold text-white">{compact(r.views)}</span></div>
                        <div>Watch time: <span className="text-neutral-300">{hours(r.watch_time_minutes)}</span></div>
                        <div>Avg view %: <span className="text-neutral-300">{r.average_view_percentage ? pct(r.average_view_percentage) : "—"}</span></div>
                      </div>
                    );
                  }}
                />
                <Bar dataKey="views" name="Views" fill={barColor} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="border-b border-white/[0.08] text-left uppercase text-neutral-400 font-mono tracking-wider">
                <tr>
                  <th className="py-2 pr-4">{firstCol}</th>
                  <th className="py-2 pr-4">Views</th>
                  <th className="py-2 pr-4">Watch time</th>
                  <th className="py-2 pr-4">Avg duration</th>
                  <th className="py-2">Avg view %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {rows.map((r) => (
                  <tr key={r.key} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-2 pr-4 font-medium text-white">{name(r.key)}</td>
                    <td className="py-2 pr-4 text-neutral-200">{compact(r.views)}</td>
                    <td className="py-2 pr-4 text-neutral-300">{hours(r.watch_time_minutes)}</td>
                    <td className="py-2 pr-4 text-neutral-400 font-mono">{r.average_view_duration_seconds == null ? "—" : clock(r.average_view_duration_seconds)}</td>
                    <td className="py-2 text-neutral-400 font-mono">{r.average_view_percentage == null ? "—" : pct(r.average_view_percentage)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Card>
  );
}

const countryName = (() => {
  try {
    const dn = new Intl.DisplayNames(["en"], { type: "region" });
    return (code: string) => dn.of(code) ?? code;
  } catch {
    return (c: string) => c;
  }
})();

export function Traffic({ range, creatorTheme }: { range: Range; creatorTheme?: CreatorPalette }) {
  return (
    <BreakdownCard
      kind="traffic-sources"
      title="Traffic Sources"
      range={range}
      name={(k) => TRAFFIC_NAMES[k] ?? k}
      firstCol="Source"
      barColor={creatorTheme?.secondary ?? "#38BDF8"}
    />
  );
}

export function Audience({ range, creatorTheme }: { range: Range; creatorTheme?: CreatorPalette }) {
  return (
    <div className="space-y-6">
      <BreakdownCard
        kind="geography"
        title="Geography"
        range={range}
        name={countryName}
        firstCol="Country"
        barColor="#A78BFA"
      />
      <BreakdownCard
        kind="devices"
        title="Devices"
        range={range}
        name={(k) => k.replace(/_/g, " ")}
        firstCol="Device"
        barColor="#4ADE80"
      />
    </div>
  );
}
