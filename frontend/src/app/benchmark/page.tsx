"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import GenreBenchmark from "@/components/intel/GenreBenchmark";
import { Loading } from "@/components/dashboard/ui";
import { api } from "@/lib/creator-api";

export default function BenchmarkPage() {
  const me = useQuery({ queryKey: ["me"], queryFn: api.me });
  return (
    <main className="mx-auto w-full max-w-6xl space-y-4 px-4 py-6 page-section-enter">
      <Link href="/dashboard" className="flex items-center gap-1 text-sm text-neutral-500 hover:underline"><ArrowLeft className="size-4" /> Dashboard</Link>
      <header>
        <p className="text-xs font-semibold tracking-[0.3em] text-red-500">RETAINAI</p>
        <h1 className="text-3xl font-bold">Genre benchmark</h1>
        <p className="text-neutral-500">Your channel next to a sample of recent public videos in a genre. Neutral comparison: no winner, no score.</p>
      </header>
      {me.isLoading && <Loading />}
      {me.data && !me.data.authenticated && (
        <p className="rounded-lg border border-neutral-400/40 p-4 text-sm">Benchmarking needs your channel data. <Link className="underline" href="/login">Connect YouTube</Link> first.</p>
      )}
      {me.data?.authenticated && <GenreBenchmark />}
    </main>
  );
}
