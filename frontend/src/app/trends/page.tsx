"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import TrendRadar from "@/components/intel/TrendRadar";

export default function TrendsPage() {
  return (
    <main className="mx-auto w-full max-w-6xl space-y-4 px-4 py-6">
      <Link href="/" className="flex items-center gap-1 text-sm text-neutral-500 hover:underline"><ArrowLeft className="size-4" /> Home</Link>
      <header>
        <p className="text-xs font-semibold tracking-[0.3em] text-red-500">RETAINAI</p>
        <h1 className="text-3xl font-bold">Trend Radar</h1>
        <p className="text-neutral-500">What&apos;s visible in recent public YouTube content for a genre. Not YouTube&apos;s algorithm — a transparent sample-based measurement.</p>
      </header>
      <TrendRadar />
    </main>
  );
}
