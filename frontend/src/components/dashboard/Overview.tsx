"use client";

import { useQuery } from "@tanstack/react-query";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type Range } from "@/lib/creator-api";
import { clock, compact, hours, pct } from "@/lib/format";
import { Card, Empty, ErrorBox, Loading, Stat, axisStyle } from "./ui";

export default function Overview({ range, subscribers }: { range: Range; subscribers: number | null }) {
  const overview = useQuery({ queryKey: ["overview", range], queryFn: () => api.overview(range) });
  const series = useQuery({ queryKey: ["timeseries", range], queryFn: () => api.timeseries(range) });
  const m = overview.data?.metrics;

  return (
    <div className="space-y-4">
      {overview.isLoading && <Loading />}
      {overview.error && <ErrorBox error={overview.error} />}
      {m && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <Stat label="Total views" value={compact(m.views)} />
            <Stat label="Watch time" value={hours(m.watch_time_minutes)} />
            <Stat label="Avg view duration" value={clock(m.average_view_duration_seconds)} />
            <Stat label="Avg view %" value={pct(m.average_view_percentage)} />
            <Stat label="Subscribers" value={compact(subscribers)} sub={m.net_subscribers != null ? `${m.net_subscribers >= 0 ? "+" : ""}${m.net_subscribers} net in range` : undefined} />
          </div>
          <div className="grid grid-cols-3 gap-3 md:grid-cols-6">
            <Stat label="Subs gained" value={compact(m.subscribers_gained)} />
            <Stat label="Subs lost" value={compact(m.subscribers_lost)} />
            <Stat label="Net subs" value={m.net_subscribers == null ? "—" : String(m.net_subscribers)} />
            <Stat label="Likes" value={compact(m.likes)} />
            <Stat label="Comments" value={compact(m.comments)} />
            <Stat label="Shares" value={compact(m.shares)} />
          </div>
        </>
      )}

      {series.error && <ErrorBox error={series.error} />}
      {series.isLoading && <Loading label="Loading charts…" />}
      {series.data && series.data.points.length === 0 && <Empty>No analytics returned for this date range.</Empty>}
      {series.data && series.data.points.length > 0 && (
        <>
          <Card title="Views over time">
            <Chart data={series.data.points} dataKey="views" name="Views" />
          </Card>
          <Card title="Watch time over time (minutes)">
            <Chart data={series.data.points} dataKey="watch_time_minutes" name="Minutes watched" />
          </Card>
          <Card title="Subscriber growth">
            <div className="h-56">
              <ResponsiveContainer>
                <BarChart data={series.data.points}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis dataKey="date" tick={axisStyle} />
                  <YAxis tick={axisStyle} />
                  <Tooltip />
                  <Bar dataKey="subscribers_gained" name="Gained" fill="#22c55e" />
                  <Bar dataKey="subscribers_lost" name="Lost" fill="#ef4444" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function Chart({ data, dataKey, name }: { data: object[]; dataKey: string; name: string }) {
  return (
    <div className="h-56">
      <ResponsiveContainer>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
          <XAxis dataKey="date" tick={axisStyle} />
          <YAxis tick={axisStyle} />
          <Tooltip />
          <Area type="monotone" dataKey={dataKey} name={name} stroke="#ef4444" fill="#ef444433" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
