"use client";

import { useEffect, useRef } from "react";

/**
 * HeroHeadline
 * ─────────────────────────────────────────────────────────
 * Renders the landing-page hero heading with:
 *   • Space Grotesk 700 (loaded via next/font/google in layout.tsx)
 *   • Line-by-line staggered entrance (translateY + opacity)
 *   • Subtle letter-spacing settle (0.04em → -0.01em)
 *   • Red colour on lines 3 & 4, white on lines 1 & 2
 *   • prefers-reduced-motion respected (instant reveal)
 */

const WHITE_LINES = ["FIND THE DROP-", "OFF"];
const RED_LINES   = ["BEFORE YOU", "PUBLISH."];
const ALL_LINES   = [...WHITE_LINES, ...RED_LINES];

// Timing (ms)
const LINE_DURATION = 650;
const LINE_STAGGER  = 110;

export default function HeroHeadline() {
  const lineRefs = useRef<(HTMLSpanElement | null)[]>([]);

  useEffect(() => {
    const prefersReduced =
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    lineRefs.current.forEach((el, i) => {
      if (!el) return;

      if (prefersReduced) {
        el.style.opacity        = "1";
        el.style.transform      = "translateY(0) translateX(0)";
        el.style.letterSpacing  = "-0.01em";
        return;
      }

      const delay  = i * LINE_STAGGER;
      const isRed  = i >= WHITE_LINES.length;

      el.style.transitionDelay         = `${delay}ms`;
      el.style.transitionDuration       = `${LINE_DURATION}ms`;
      el.style.transitionProperty       = "opacity, transform, letter-spacing";
      el.style.transitionTimingFunction = "cubic-bezier(0.16, 1, 0.3, 1)";

      // Double-rAF: ensure browser has committed the initial (hidden) state
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          el.style.opacity       = "1";
          el.style.transform     = "translateY(0) translateX(0)";
          el.style.letterSpacing = isRed ? "-0.01em" : "-0.01em";
        });
      });
    });
  }, []);

  return (
    <h1
      className="hero-headline"
      aria-label="Find the Drop-Off Before You Publish."
    >
      {ALL_LINES.map((line, i) => {
        const isRed  = i >= WHITE_LINES.length;
        const isLast = i === ALL_LINES.length - 1;
        return (
          <span
            key={i}
            ref={(el) => { lineRefs.current[i] = el; }}
            className={[
              "hero-line",
              isRed  ? "hero-line--red"  : "",
              isLast ? "hero-line--last" : "",
            ].filter(Boolean).join(" ")}
            style={{
              /* Initial (hidden) state — useEffect animates to final */
              opacity:       0,
              transform:     isRed
                ? "translateY(35px) translateX(-8px)"
                : "translateY(35px)",
              letterSpacing: "0.04em",   /* slightly wide — settles to -0.01em */
              display:       "block",
              willChange:    "opacity, transform",
            }}
            aria-hidden="true"
          >
            {line}
          </span>
        );
      })}
    </h1>
  );
}
