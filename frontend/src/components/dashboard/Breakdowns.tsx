"use client";

import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type BreakdownRow, type Range } from "@/lib/creator-api";
import { clock, compact, hours, pct } from "@/lib/format";
import { Card, Empty, ErrorBox, Loading, axisStyle } from "./ui";

const TRAFFIC_NAMES: Record<string, string> = {
  YT_SEARCH: "YouTube Search", RELATED_VIDEO: "Suggested Videos", YT_OTHER_PAGE: "Browse Features",
  EXT_URL: "External", NO_LINK_OTHER: "Direct or Unknown", PLAYLIST: "Playlists", SUBSCRIBER: "Subscriptions",
  YT_CHANNEL: "Channel Pages", NOTIFICATION: "Notifications", END_SCREEN: "End Screens", SHORTS: "Shorts Feed",
};

function BreakdownCard({ kind, title, range, name, firstCol }: { kind: "traffic-sources" | "geography" | "devices"; title: string; range: Range; name: (k: string) => string; firstCol: string }) {
  const q = useQuery({ queryKey: [kind, range], queryFn: () => api.breakdown(kind, range) });
  const rows: BreakdownRow[] = q.data?.rows ?? [];
  return (
    <Card title={title}>
      {q.isLoading && <Loading />}
      {q.error && <ErrorBox error={q.error} />}
      {q.data && rows.length === 0 && <Empty>No data returned for this date range.</Empty>}
      {rows.length > 0 && (
        <>
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={rows.map((r) => ({ ...r, label: name(r.key) }))} layout="vertical" margin={{ left: 40 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis type="number" tick={axisStyle} />
                <YAxis type="category" dataKey="label" tick={axisStyle} width={110} />
                <Tooltip />
                <Bar dataKey="views" name="Views" fill="#ef4444" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <table className="mt-3 w-full text-sm">
            <thead className="text-left text-xs uppercase text-neutral-500">
              <tr><th>{firstCol}</th><th>Views</th><th>Watch time</th><th>Avg duration</th><th>Avg view %</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key} className="border-t border-neutral-400/20">
                  <td className="py-1">{name(r.key)}</td>
                  <td>{compact(r.views)}</td>
                  <td>{hours(r.watch_time_minutes)}</td>
                  <td>{r.average_view_duration_seconds == null ? "—" : clock(r.average_view_duration_seconds)}</td>
                  <td>{r.average_view_percentage == null ? "—" : pct(r.average_view_percentage)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </Card>
  );
}

const countryName = (() => {
  try {
    const dn = new Intl.DisplayNames(["en"], { type: "region" });
    return (c: string) => dn.of(c) ?? c;
  } catch {
    return (c: string) => c;
  }
})();

export function Traffic({ range }: { range: Range }) {
  return <BreakdownCard kind="traffic-sources" title="Traffic Sources" range={range} firstCol="Source" name={(k) => TRAFFIC_NAMES[k] ?? k.replaceAll("_", " ").toLowerCase()} />;
}

export function Audience({ range }: { range: Range }) {
  return (
    <div className="space-y-4">
      <BreakdownCard kind="geography" title="Top Viewer Countries" range={range} firstCol="Country" name={countryName} />
      <BreakdownCard kind="devices" title="Viewer Devices" range={range} firstCol="Device" name={(k) => k.replaceAll("_", " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase())} />
    </div>
  );
}
