"use client";

import React from "react";

interface InfinityLoopProps {
  className?: string;
  size?: "sm" | "md" | "lg";
  glow?: boolean;
}

/**
 * RetainAI Brand InfinityLoop Loading Indicator
 *
 * Mathematical Lemniscate of Bernoulli curve with a continuous,
 * flowing stroke pulse that seamlessly travels around the figure-eight.
 * Uses CSS variables (--creator-primary / #67E8F9) for theme harmony.
 */
export default function InfinityLoop({
  className = "h-16 w-24",
  glow = true,
}: InfinityLoopProps) {
  return (
    <div className={`relative inline-flex items-center justify-center ${className}`}>
      {/* Subtle creator-accent ambient glow behind the loop */}
      {glow && (
        <div
          className="pointer-events-none absolute inset-0 -m-3 rounded-full blur-xl opacity-25"
          style={{
            background:
              "radial-gradient(ellipse at center, var(--creator-primary, #67E8F9) 0%, transparent 70%)",
          }}
          aria-hidden="true"
        />
      )}

      <svg
        viewBox="0 0 100 50"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full relative z-10"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="infinityGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--creator-primary, #67E8F9)" stopOpacity="0.3" />
            <stop offset="50%" stopColor="var(--creator-primary, #67E8F9)" stopOpacity="1" />
            <stop offset="100%" stopColor="var(--creator-primary, #67E8F9)" stopOpacity="0.3" />
          </linearGradient>
        </defs>

        {/* Static faint background track */}
        <path
          d="M 50 25 C 62 10, 88 10, 88 25 C 88 40, 62 40, 50 25 C 38 10, 12 10, 12 25 C 12 40, 38 40, 50 25 Z"
          stroke="var(--creator-primary, #67E8F9)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.15"
        />

        {/* Animated fluid pulse traveling along the infinity track */}
        <path
          d="M 50 25 C 62 10, 88 10, 88 25 C 88 40, 62 40, 50 25 C 38 10, 12 10, 12 25 C 12 40, 38 40, 50 25 Z"
          pathLength="100"
          stroke="url(#infinityGrad)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray="28 72"
          className="infinity-loop-pulse"
        />
      </svg>
    </div>
  );
}
