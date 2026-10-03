"use client";

import React from "react";
import InfinityLoop from "./InfinityLoop";

interface RetainLoadingStateProps {
  title: string;
  subtitle?: string | null;
  className?: string;
  loopSize?: string;
  minHeight?: string;
}

/**
 * Unified RetainAI Brand Loading Experience
 *
 * Pattern:
 *               ∞
 *         PRIMARY STATUS
 *        secondary status
 *
 * Centered in the workspace with fluid status transitions,
 * accessibility live-region semantics, and brand visual harmony.
 */
export default function RetainLoadingState({
  title,
  subtitle,
  className = "",
  loopSize = "h-16 w-24",
  minHeight = "min-h-[360px]",
}: RetainLoadingStateProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`relative flex flex-col items-center justify-center p-8 text-center select-none ${minHeight} ${className}`}
    >
      {/* Centered Brand InfinityLoop */}
      <InfinityLoop className={loopSize} />

      {/* Primary & Contextual Secondary Status */}
      <div className="mt-6 space-y-1.5 max-w-md">
        <h3
          key={title}
          className="text-xl sm:text-2xl font-semibold text-white tracking-tight animate-status-fade"
        >
          {title}
        </h3>

        {subtitle && (
          <p
            key={subtitle}
            className="text-xs sm:text-sm text-neutral-400 font-normal leading-relaxed animate-status-fade"
          >
            {subtitle}
          </p>
        )}
      </div>

      <span className="sr-only">
        {title} {subtitle ? `— ${subtitle}` : ""}
      </span>
    </div>
  );
}
