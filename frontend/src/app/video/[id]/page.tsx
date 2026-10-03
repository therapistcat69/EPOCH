"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import VideoReport from "@/components/intel/VideoReport";

export default function VideoPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <main className="mx-auto w-full max-w-6xl space-y-4 px-4 py-6">
      <Link href="/dashboard" className="flex items-center gap-1 text-sm text-neutral-500 hover:underline">
        <ArrowLeft className="size-4" /> Dashboard
      </Link>
      <VideoReport videoId={id} />
    </main>
  );
}
