"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3, Clock, Globe, LineChart, ShieldCheck, TrendingDown } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";
import { friendlyMessage } from "@/lib/api";
import { api, loginUrl } from "@/lib/creator-api";

function LoginInner() {
  const router = useRouter();
  const error = useSearchParams().get("error");
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });

  useEffect(() => {
    if (me.data?.authenticated) router.replace("/dashboard");
  }, [me.data, router]);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-xl flex-col justify-center px-6 py-12">
      <p className="text-sm font-semibold tracking-[0.3em] text-red-500">RETAINAI</p>
      <h1 className="mt-3 text-4xl font-bold leading-tight">
        Turn YouTube Analytics into
        <br />
        pre-publication intelligence.
      </h1>
      <p className="mt-4 text-neutral-500">Connect your channel to see:</p>
      <ul className="mt-2 space-y-2">
        {[
          [BarChart3, "Video performance"],
          [TrendingDown, "Audience retention"],
          [Clock, "Watch time"],
          [Globe, "Traffic sources"],
          [LineChart, "Historical content performance"],
        ].map(([Icon, label]) => {
          const I = Icon as typeof BarChart3;
          return (
            <li key={label as string} className="flex items-center gap-2">
              <I className="size-4 text-red-500" /> {label as string}
            </li>
          );
        })}
      </ul>

      {error && (
        <p role="alert" className="mt-6 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-500">
          {friendlyMessage(error)}
        </p>
      )}

      <a href={loginUrl} className="mt-8 inline-flex items-center justify-center rounded-lg bg-red-600 px-5 py-3 font-semibold text-white hover:bg-red-700">
        Continue with YouTube
      </a>
      <p className="mt-4 flex items-center gap-2 text-sm text-neutral-500">
        <ShieldCheck className="size-4" /> Read-only access. No videos are uploaded, edited or deleted.
      </p>
      <Link href="/" className="mt-8 text-sm text-neutral-500 hover:underline">
        ← Analyze a public video without signing in
      </Link>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginInner />
    </Suspense>
  );
}
