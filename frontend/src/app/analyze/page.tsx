"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { api } from "@/lib/creator-api";
import PublicAnalyzer from "@/components/PublicAnalyzer";
import RetainLoadingState from "@/components/RetainLoadingState";

/**
 * /analyze — Authenticated analysis workspace.
 *
 * Reuses the existing PublicAnalyzer component (all API calls, logic,
 * and UI intact). Auth-guarded with the same api.me pattern used by
 * the dashboard. No backend changes.
 */
export default function AnalyzePage() {
  const router = useRouter();

  const me = useQuery({ queryKey: ["me"], queryFn: api.me });

  useEffect(() => {
    // Not loading and definitively unauthenticated → redirect to login
    if (!me.isLoading && me.data && !me.data.authenticated) {
      router.replace("/login");
    }
  }, [me.isLoading, me.data, router]);

  // Loading state
  if (me.isLoading) {
    return (
      <div className="min-h-screen w-full bg-[#030303] flex items-center justify-center">
        <RetainLoadingState
          title="Verifying creator session"
          subtitle="Preparing analysis workspace..."
        />
      </div>
    );
  }

  // Redirecting (not authenticated)
  if (!me.data?.authenticated) {
    return (
      <div className="min-h-screen w-full bg-[#030303] flex items-center justify-center">
        <RetainLoadingState
          title="Redirecting"
          subtitle="Please sign in to access analysis..."
        />
      </div>
    );
  }

  // Authenticated — render the analysis workspace
  return (
    <div className="min-h-screen w-full bg-[#030303] text-white selection:bg-[#ff1f3d] selection:text-white page-section-enter">
      {/* ── Top bar matching dashboard language ── */}
      <header className="border-b border-white/[0.08] bg-[#030303] sticky top-0 z-20">
        <div className="mx-auto w-full max-w-5xl px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <a
              href="/dashboard"
              className="text-xs font-semibold text-neutral-500 hover:text-white transition-colors duration-150"
            >
              ← Dashboard
            </a>
            <div className="h-4 w-[1px] bg-white/10" />
            <span className="text-sm font-black tracking-[0.25em] text-[#ff1f3d]">
              RETAINAI
            </span>
            <div className="h-4 w-[1px] bg-white/10" />
            <span className="text-xs font-semibold text-neutral-300 tracking-wide">
              Analyze
            </span>
          </div>

          {me.data?.user?.name && (
            <span className="text-xs text-neutral-500 font-mono hidden sm:block">
              {me.data.user.name}
            </span>
          )}
        </div>
      </header>

      {/* ── Analysis workspace ── */}
      {/*
        PublicAnalyzer is rendered completely unchanged.
        All API calls, mutation logic, routing to /report/:id,
        TranscriptAnalyzer, ModelProvenance, and Recent Analyses
        remain exactly as they were.
      */}
      <PublicAnalyzer />
    </div>
  );
}
