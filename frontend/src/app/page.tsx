"use client";

import { useCallback, useEffect, useRef } from "react";
import Link from "next/link";
import TiltedCard from "@/components/TiltedCard";
import HeroHeadline from "@/components/HeroHeadline";

export default function Home() {
  /* ── Parallax layer refs ── */
  const bgRef      = useRef<HTMLDivElement>(null);
  const charRef    = useRef<HTMLDivElement>(null);
  const textColRef = useRef<HTMLDivElement>(null);
  const rafRef     = useRef<number | null>(null);

  /* ── Mouse parallax (GPU-only: transform/opacity) ── */
  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (rafRef.current) return;

    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;

      const cx = window.innerWidth  / 2;
      const cy = window.innerHeight / 2;
      const dx = (e.clientX - cx) / cx; // −1 … +1
      const dy = (e.clientY - cy) / cy;

      if (bgRef.current) {
        bgRef.current.style.transform =
          `translate(${dx * 6}px, ${dy * 6}px) scale(1.02)`;
      }
      if (charRef.current) {
        charRef.current.style.transform =
          `translate(${dx * 4}px, ${dy * 4}px)`;
      }
      if (textColRef.current) {
        textColRef.current.style.transform =
          `translate(${dx * 1.5}px, ${dy * 1.5}px)`;
      }
    });
  }, []);

  useEffect(() => {
    const prefersReduced =
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) return;

    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [handleMouseMove]);

  return (
    <main
      className="relative w-full h-screen overflow-hidden flex flex-col justify-center bg-black text-slate-100 selection:bg-red-600/30 selection:text-red-200"
    >
      {/* ── Hero Background (parallax layer) ── */}
      <div
        ref={bgRef}
        className="absolute inset-0 will-change-transform"
        style={{
          backgroundImage:    "url('/hero-bg.jpg')",
          backgroundSize:     "cover",
          backgroundPosition: "center",
          backgroundRepeat:   "no-repeat",
          transition:         "transform 80ms linear",
        }}
        aria-hidden="true"
      />

      {/* ── Cinematic gradient overlay ── */}
      <div
        className="absolute inset-0 pointer-events-none z-[1]"
        style={{
          background:
            "linear-gradient(90deg, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.72) 36%, rgba(0,0,0,0.22) 64%, rgba(0,0,0,0.0) 100%), linear-gradient(180deg, rgba(0,0,0,0.4) 0%, rgba(0,0,0,0.0) 25%, rgba(0,0,0,0.0) 75%, rgba(0,0,0,0.6) 100%)",
        }}
        aria-hidden="true"
      />

      {/* ── FULL-SCREEN TWO-COLUMN HERO COMPOSITION ── */}
      <div className="relative z-10 mx-auto w-full max-w-7xl px-6 sm:px-8 lg:px-12 flex-1 flex items-center">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 w-full items-center">

          {/* LEFT COLUMN */}
          <div
            ref={textColRef}
            className="lg:col-span-7 xl:col-span-7 flex flex-col justify-center max-w-[620px] text-left will-change-transform"
            style={{ transition: "transform 80ms linear" }}
          >
            <HeroHeadline />

            <p className="hero-desc mt-6 text-base sm:text-lg lg:text-xl text-neutral-300 font-normal leading-relaxed max-w-[520px]">
              AI-powered video retention analysis that predicts where viewers
              may lose interest and tells you exactly what to fix.
            </p>

            <div className="mt-8 sm:mt-10 flex flex-wrap items-center gap-4">
              <Link
                href="/login"
                id="btn-login"
                className="btn-red-fill hero-btn-1"
              >
                <span className="btn-content"><span>LOGIN</span></span>
              </Link>

              <Link
                href="/signup"
                id="btn-signup"
                className="btn-red-secondary hero-btn-2"
              >
                <span className="btn-content"><span>SIGN UP</span></span>
              </Link>
            </div>
          </div>

          {/* RIGHT COLUMN: CHARACTER */}
          <div
            id="creator-character-stage"
            ref={charRef}
            className="lg:col-span-5 xl:col-span-5 relative w-full flex items-center justify-center lg:justify-end xl:justify-center py-4 lg:py-0 will-change-transform"
            aria-label="RetainAI Creator Character"
            style={{ transition: "transform 80ms linear" }}
          >
            <div className="character-float animate-character">
              <TiltedCard
                imageSrc="/images/retainai-character.png"
                altText="RetainAI Creator Character"
                containerWidth="100%"
                containerHeight="100%"
                imageWidth="100%"
                imageHeight="100%"
                rotateAmplitude={8}
                scaleOnHover={1.03}
                showMobileWarning={false}
                showTooltip={false}
                displayOverlayContent={false}
                className="w-full max-w-[340px] sm:max-w-[420px] md:max-w-[460px] lg:max-w-[500px] xl:max-w-[520px] aspect-square"
              />
            </div>
          </div>

        </div>
      </div>
    </main>
  );
}