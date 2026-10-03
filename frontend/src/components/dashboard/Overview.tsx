"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Clock,
  Eye,
  MessageSquare,
  Percent,
  Share2,
  ThumbsUp,
  TrendingUp,
  UserMinus,
  UserPlus,
  Users,
} from "lucide-react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type Range } from "@/lib/creator-api";
import type { CreatorPalette } from "@/lib/creatorTheme";
import { clock, compact, hours, pct } from "@/lib/format";
import { Card, Empty, ErrorBox, Loading, Stat, axisStyle } from "./ui";

interface OverviewProps {
  range: Range;
  subscribers: number | null;
  creatorTheme?: CreatorPalette;
}

export default function Overview({ range, subscribers, creatorTheme }: OverviewProps) {
  const overview = useQuery({ queryKey: ["overview", range], queryFn: () => api.overview(range) });
  const series = useQuery({ queryKey: ["timeseries", range], queryFn: () => api.timeseries(range) });
  const m = overview.data?.metrics;

  const accent = creatorTheme?.primary ?? "#67E8F9";

  return (
    <div className="space-y-6">
      {overview.isLoading && <Loading label="Loading creator overview..." />}
      {overview.error && <ErrorBox error={overview.error} />}

      {m && (
        <div className="space-y-4">
          {/* Top 5 Primary Metric Cards */}
          <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-5">
            <Stat
              label="Total views"
              value={compact(m.views)}
              icon={<Eye className="size-4" />}
              accentColor="#7DD3FC"
            />
            <Stat
              label="Watch time"
              value={hours(m.watch_time_minutes)}
              icon={<Clock className="size-4" />}
              accentColor="#C4B5FD"
            />
            <Stat
              label="Avg view duration"
              value={clock(m.average_view_duration_seconds)}
              icon={<TrendingUp className="size-4" />}
              accentColor="#93C5FD"
            />
            <Stat
              label="Avg view %"
              value={pct(m.average_view_percentage)}
              icon={<Percent className="size-4" />}
              accentColor={accent}
            />
            <Stat
              label="Subscribers"
              value={compact(subscribers)}
              sub={m.net_subscribers != null ? `${m.net_subscribers >= 0 ? "+" : ""}${m.net_subscribers} net` : undefined}
              icon={<Users className="size-4" />}
              accentColor="#86EFAC"
            />
          </div>

          {/* Secondary Metrics Bar */}
          <div className="grid grid-cols-3 gap-3 md:grid-cols-6">
            <Stat
              label="Subs gained"
              value={compact(m.subscribers_gained)}
              icon={<UserPlus className="size-3.5" />}
              accentColor="#86EFAC"
            />
            <Stat
              label="Subs lost"
              value={compact(m.subscribers_lost)}
              icon={<UserMinus className="size-3.5" />}
              accentColor="#FDA4AF"
            />
            <Stat
              label="Net subs"
              value={m.net_subscribers == null ? "—" : String(m.net_subscribers)}
              icon={<Users className="size-3.5" />}
            />
            <Stat
              label="Likes"
              value={compact(m.likes)}
              icon={<ThumbsUp className="size-3.5" />}
              accentColor="#FDA4AF"
            />
            <Stat
              label="Comments"
              value={compact(m.comments)}
              icon={<MessageSquare className="size-3.5" />}
              accentColor="#FCD34D"
            />
            <Stat
              label="Shares"
              value={compact(m.shares)}
              icon={<Share2 className="size-3.5" />}
              accentColor="#38BDF8"
            />
          </div>
        </div>
      )}

      {series.error && <ErrorBox error={series.error} />}
      {series.isLoading && <Loading label="Loading analytics charts…" />}
      {series.data && series.data.points.length === 0 && (
        <Empty>No analytics returned for this date range.</Empty>
      )}

      {series.data && series.data.points.length > 0 && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Views Chart (Light Blue) */}
          <Card title="Views over time">
            <AreaChartComponent
              data={series.data.points}
              dataKey="views"
              name="Views"
              strokeColor="#38BDF8"
              gradientId="viewsAreaGrad"
            />
          </Card>

          {/* Watch Time Chart (Light Purple) */}
          <Card title="Watch time (minutes)">
            <AreaChartComponent
              data={series.data.points}
              dataKey="watch_time_minutes"
              name="Minutes watched"
              strokeColor="#A78BFA"
              gradientId="watchAreaGrad"
            />
          </Card>

          {/* Subscriber Growth Chart (Mint Green & Soft Coral) */}
          <div className="lg:col-span-2">
            <Card title="Subscriber growth">
              <div className="h-64 pt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={series.data.points}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="date" tick={axisStyle} stroke="rgba(255,255,255,0.2)" />
                    <YAxis tick={axisStyle} stroke="rgba(255,255,255,0.2)" />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="subscribers_gained" name="Gained" fill="#4ADE80" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="subscribers_lost" name="Lost" fill="#FB7185" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

function AreaChartComponent({
  data,
  dataKey,
  name,
  strokeColor,
  gradientId,
}: {
  data: object[];
  dataKey: string;
  name: string;
  strokeColor: string;
  gradientId: string;
}) {
  return (
    <div className="h-64 pt-2">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={strokeColor} stopOpacity={0.35} />
              <stop offset="95%" stopColor={strokeColor} stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis dataKey="date" tick={axisStyle} stroke="rgba(255,255,255,0.2)" />
          <YAxis tick={axisStyle} stroke="rgba(255,255,255,0.2)" />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey={dataKey}
            name={name}
            stroke={strokeColor}
            strokeWidth={2}
            fill={`url(#${gradientId})`}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

type TooltipEntry = { name?: string; value?: number | string; color?: string; stroke?: string; fill?: string };

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: TooltipEntry[]; label?: string }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="rounded-xl border border-white/10 bg-[#0c0d14]/95 backdrop-blur-xl p-3 shadow-2xl text-xs">
      <div className="font-semibold text-neutral-300 mb-1 font-mono">{label}</div>
      {payload.map((entry, index) => (
        <div key={index} className="flex items-center gap-2 py-0.5">
          <div className="size-2 rounded-full" style={{ backgroundColor: entry.color || entry.stroke || entry.fill }} />
          <span className="text-neutral-400 capitalize">{entry.name}:</span>
          <span className="font-bold text-white">{Number(entry.value).toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}
