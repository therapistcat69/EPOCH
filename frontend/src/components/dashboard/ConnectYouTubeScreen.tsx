"use client";

import { AlertCircle, CheckCircle2, Lock, LogOut, ShieldCheck } from "lucide-react";
import React, { useState } from "react";

import LogoutButton from "./LogoutButton";

interface ConnectYouTubeScreenProps {
  userName?: string | null;
  userEmail?: string | null;
  loginUrl: string;
  onLogout: () => void;
  isLoggingOut?: boolean;
  errorMessage?: string | null;
}

export default function ConnectYouTubeScreen({
  userName,
  userEmail,
  loginUrl,
  onLogout,
  isLoggingOut = false,
  errorMessage = null,
}: ConnectYouTubeScreenProps) {
  const [isConnecting, setIsConnecting] = useState(false);

  const handleConnect = () => {
    if (isConnecting) return;
    setIsConnecting(true);
    // Smooth transition before OAuth redirect
    setTimeout(() => {
      window.location.href = loginUrl;
    }, 180);
  };

  return (
    <div className="relative min-h-screen w-full bg-[#030303] text-white flex flex-col justify-between overflow-hidden select-none">
      {/* ============================================================
          ATMOSPHERIC AMBIENT RGB GLOWS (Subtle Environmental Light)
          ============================================================ */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {/* Top-Left: Subtle Red Glow */}
        <div
          className="atmospheric-glow-a absolute -top-[18%] -left-[10%] w-[580px] h-[580px] rounded-full blur-[140px]"
          style={{ background: "radial-gradient(circle, rgba(255, 31, 61, 0.12) 0%, rgba(255, 31, 61, 0) 70%)" }}
        />

        {/* Top-Right: Subtle Purple / Blue Glow */}
        <div
          className="atmospheric-glow-b absolute -top-[20%] -right-[8%] w-[640px] h-[640px] rounded-full blur-[150px]"
          style={{ background: "radial-gradient(circle, rgba(139, 92, 246, 0.09) 0%, rgba(59, 130, 246, 0.04) 50%, rgba(0, 0, 0, 0) 75%)" }}
        />

        {/* Bottom-Left: Subtle Magenta Glow */}
        <div
          className="atmospheric-glow-b absolute -bottom-[22%] -left-[12%] w-[560px] h-[560px] rounded-full blur-[150px]"
          style={{ background: "radial-gradient(circle, rgba(236, 72, 153, 0.08) 0%, rgba(217, 70, 239, 0.02) 50%, rgba(0, 0, 0, 0) 70%)" }}
        />

        {/* Bottom-Right: Subtle Cyan / Deep Blue Glow */}
        <div
          className="atmospheric-glow-a absolute -bottom-[18%] -right-[10%] w-[600px] h-[600px] rounded-full blur-[140px]"
          style={{ background: "radial-gradient(circle, rgba(6, 182, 212, 0.08) 0%, rgba(37, 99, 235, 0.04) 50%, rgba(0, 0, 0, 0) 75%)" }}
        />

        {/* Center Vignette: Ensures Center Remains Dark & Readable */}
        <div className="absolute inset-0 bg-radial-vignette opacity-70" />
      </div>

      {/* ============================================================
          TOP HEADER
          ============================================================ */}
      <header className="relative z-10 w-full max-w-6xl mx-auto px-6 py-6 flex items-center justify-between border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <span className="text-sm font-black tracking-[0.3em] text-[#ff1f3d]">RETAINAI</span>
          <span className="text-[11px] text-neutral-500 font-mono tracking-wider">
            | {userName || userEmail || "CREATOR"}
          </span>
        </div>

        <LogoutButton onLogout={onLogout} isLoggingOut={isLoggingOut} />
      </header>

      {/* ============================================================
          MAIN CONNECTION EXPERIENCE (Shifted slightly upward for balance)
          ============================================================ */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-4 py-8">
        <div className="w-full max-w-xl mx-auto flex flex-col items-center -mt-4">
          {/* Error Banner if Redirected with Error */}
          {errorMessage && (
            <div className="mb-6 w-full flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-950/40 p-3.5 text-xs text-red-200 backdrop-blur-md">
              <AlertCircle className="size-4 text-red-400 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Connection Glass Card */}
          <div className="connection-glass-card w-full rounded-2xl p-8 sm:p-11 text-center">
            {/* Subtle YouTube Icon in Glass Circle Container */}
            <div className="mx-auto mb-6 flex size-14 items-center justify-center rounded-full bg-black/60 border border-[#ff1f3d]/30 shadow-[0_0_25px_rgba(255,31,61,0.22)]">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="#ff1f3d" className="translate-x-[0.5px]">
                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
              </svg>
            </div>

            {/* Main Heading: Large Bold White Typography */}
            <h1 className="text-2xl sm:text-3xl md:text-4xl font-extrabold tracking-tight text-white uppercase leading-[1.15] mb-4">
              CONNECT YOUR <br />
              <span className="text-white">YOUTUBE CHANNEL<span className="text-[#ff1f3d]">.</span></span>
            </h1>

            {/* Supporting Copy */}
            <p className="text-sm sm:text-[15px] text-neutral-300 font-normal leading-relaxed max-w-md mx-auto mb-8">
              Give RetainAI access to your channel analytics so we can uncover where your audience may lose interest.
            </p>

            {/* Primary Action Button (RetainAI Left-to-Right Red Fill) */}
            <div className="w-full max-w-sm mx-auto">
              <button
                type="button"
                id="connect-youtube-channel-btn"
                onClick={handleConnect}
                disabled={isConnecting}
                className="retain-connect-btn w-full rounded-xl py-3.5 px-6 text-xs sm:text-[13px] tracking-wider shadow-lg"
              >
                {isConnecting ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="size-3.5 rounded-full border-2 border-current border-t-transparent animate-spin" />
                    CONNECTING TO YOUTUBE...
                  </span>
                ) : (
                  <span>CONNECT YOUTUBE CHANNEL →</span>
                )}
              </button>
            </div>

            {/* Read-Only Security / Trust Message */}
            <div className="mt-6 flex items-center justify-center gap-2 text-[11px] text-white/50 tracking-wide">
              <ShieldCheck className="size-3.5 text-[#ff1f3d]/80 shrink-0" />
              <span>
                <strong className="text-white/70 font-medium">Read-only access.</strong> RetainAI cannot upload, edit, or delete your videos.
              </span>
            </div>
          </div>

          {/* ============================================================
              THREE-STEP PROGRESS VISUAL (Subtle, Muted Explainer)
              ============================================================ */}
          <div className="mt-8 w-full max-w-lg px-2">
            <div className="grid grid-cols-3 gap-3 text-center">
              {/* Step 1 */}
              <div className="flex flex-col items-center p-2 rounded-lg bg-white/[0.015] border border-white/[0.04]">
                <span className="text-[10px] font-mono font-bold tracking-widest text-[#ff1f3d]">01 CONNECT</span>
                <span className="text-[11px] text-neutral-300 mt-0.5">Link Channel</span>
              </div>

              {/* Step 2 */}
              <div className="flex flex-col items-center p-2 rounded-lg bg-white/[0.015] border border-white/[0.04]">
                <span className="text-[10px] font-mono font-bold tracking-widest text-neutral-500">02 ANALYZE</span>
                <span className="text-[11px] text-neutral-400 mt-0.5">Audience Curves</span>
              </div>

              {/* Step 3 */}
              <div className="flex flex-col items-center p-2 rounded-lg bg-white/[0.015] border border-white/[0.04]">
                <span className="text-[10px] font-mono font-bold tracking-widest text-neutral-500">03 IMPROVE</span>
                <span className="text-[11px] text-neutral-400 mt-0.5">Before Publishing</span>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* ============================================================
          SUBTLE FOOTER
          ============================================================ */}
      <footer className="relative z-10 w-full max-w-6xl mx-auto px-6 py-4 flex items-center justify-between text-[11px] text-neutral-600 border-t border-white/[0.04]">
        <span>© 2026 RETAINAI · RETENTION INTELLIGENCE</span>
        <span className="font-mono">SECURE OAUTH 2.0 PROTOCOL</span>
      </footer>
    </div>
  );
}
