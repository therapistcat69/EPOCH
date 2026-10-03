"use client";

import { AlertCircle, Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import RetainLoadingState from "@/components/RetainLoadingState";
import InfinityLoop from "@/components/InfinityLoop";

export function Card({
  title,
  children,
  right,
  className = "",
}: {
  title?: string;
  children: ReactNode;
  right?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-2xl border border-white/[0.08] bg-[#09090d]/85 backdrop-blur-xl p-5 shadow-2xl transition-all duration-200 hover:border-white/[0.13] ${className}`}>
      {(title || right) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.05] pb-3">
          <h2 className="text-sm font-semibold tracking-wide text-white uppercase">{title}</h2>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({
  label,
  value,
  sub,
  icon,
  accentColor,
  className = "",
}: {
  label: string;
  value: string;
  sub?: string;
  icon?: ReactNode;
  accentColor?: string;
  className?: string;
}) {
  return (
    <div className={`relative overflow-hidden rounded-2xl border border-white/[0.08] bg-[#09090d]/85 backdrop-blur-xl p-4 shadow-lg transition-all duration-200 hover:border-white/[0.14] ${className}`}>
      {accentColor && (
        <div
          className="absolute top-0 left-0 right-0 h-[2px] opacity-80"
          style={{ backgroundColor: accentColor }}
        />
      )}
      <div className="flex items-center justify-between gap-2">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-neutral-400">{label}</div>
        {icon && (
          <div
            className="flex size-7 items-center justify-center rounded-lg bg-white/[0.03] border border-white/[0.06]"
            style={accentColor ? { color: accentColor } : undefined}
          >
            {icon}
          </div>
        )}
      </div>
      <div className="mt-2 text-2xl font-bold tracking-tight text-white">{value}</div>
      {sub && <div className="mt-1 text-xs text-neutral-400 font-medium">{sub}</div>}
    </div>
  );
}

export function Loading({
  label = "Loading your dashboard",
  sub = "Fetching your latest data...",
  compact = false,
}: {
  label?: string;
  sub?: string;
  compact?: boolean;
}) {
  if (compact) {
    return (
      <div role="status" className="flex items-center justify-center gap-2.5 py-4 text-xs text-neutral-400">
        <InfinityLoop className="h-5 w-8" glow={false} />
        <span className="font-mono text-[11px] uppercase tracking-wider">{label}</span>
      </div>
    );
  }

  return (
    <RetainLoadingState
      title={label}
      subtitle={sub}
      minHeight="min-h-[260px]"
    />
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  return (
    <div role="alert" className="flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-950/30 p-4 text-xs text-red-200 backdrop-blur-md">
      <AlertCircle className="size-4 text-red-400 shrink-0" />
      <span>{error instanceof Error ? error.message : "Something went wrong."}</span>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="py-12 text-center text-xs text-neutral-500 font-mono uppercase tracking-wider">
      {children}
    </div>
  );
}

export const axisStyle = { fontSize: 11, fill: "rgba(255, 255, 255, 0.45)" };
