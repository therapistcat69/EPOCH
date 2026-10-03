"use client";

import Link from "next/link";
import PublicAnalyzer from "@/components/PublicAnalyzer";
import TiltedCard from "@/components/TiltedCard";

export default function Home() {
  return (
    <>
    <main
      className="relative w-full min-h-screen lg:h-screen lg:min-h-screen overflow-x-hidden overflow-y-auto lg:overflow-hidden flex flex-col justify-center bg-black text-slate-100 selection:bg-red-600/30 selection:text-red-200"
      style={{
        backgroundImage: "url('/hero-bg.jpg')",
        backgroundSize: "cover",
        backgroundPosition: "center",
        backgroundRepeat: "no-repeat",
      }}
    >
      {/* Subtle Dark Neutral Overlay for Text Legibility (No heavy tint) */}
      <div
        className="absolute inset-0 pointer-events-none z-[1]"
        style={{
          background:
            "linear-gradient(90deg, rgba(0, 0, 0, 0.88) 0%, rgba(0, 0, 0, 0.72) 36%, rgba(0, 0, 0, 0.22) 64%, rgba(0, 0, 0, 0.0) 100%), linear-gradient(180deg, rgba(0, 0, 0, 0.4) 0%, rgba(0, 0, 0, 0.0) 25%, rgba(0, 0, 0, 0.0) 75%, rgba(0, 0, 0, 0.6) 100%)",
        }}
        aria-hidden="true"
      />

      {/* FULL-SCREEN TWO-COLUMN HERO COMPOSITION */}
      <div className="relative z-10 mx-auto w-full max-w-7xl px-6 sm:px-8 lg:px-12 py-12 lg:py-0 flex-1 flex items-center">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 w-full items-center">
          {/* LEFT COLUMN: HERO CONTENT */}
          <div className="lg:col-span-7 xl:col-span-7 flex flex-col justify-center max-w-[620px] text-left">
            {/* Bold Headline */}
            <h1 className="animate-headline text-4xl sm:text-5xl md:text-6xl lg:text-[4.25rem] xl:text-[4.85rem] font-black tracking-tight leading-[1.03] text-white uppercase">
              FIND THE DROP-OFF
              <br />
              <span className="text-[#ff1a1a]">BEFORE YOU PUBLISH.</span>
            </h1>

            {/* Supporting Description */}
            <p className="animate-desc mt-6 text-base sm:text-lg lg:text-xl text-neutral-300 font-normal leading-relaxed max-w-[520px]">
              AI-powered video retention analysis that predicts where viewers may lose interest and tells you exactly what to fix.
            </p>

            {/* ONLY TWO CTA BUTTONS: LOGIN & SIGN UP */}
            <div className="animate-cta mt-8 sm:mt-10 flex flex-wrap items-center gap-4">
              {/* 1. LOGIN BUTTON */}
              <Link
                href="/login"
                id="btn-login"
                className="btn-red-fill"
              >
                <span className="btn-content">
                  <span>LOGIN</span>
                </span>
              </Link>

              {/* 2. SIGN UP BUTTON */}
              <Link
                href="/signup"
                id="btn-signup"
                className="btn-red-secondary"
              >
                <span className="btn-content">
                  <span>SIGN UP</span>
                </span>
              </Link>
            </div>
            <a href="#analyze" className="mt-5 inline-block text-sm text-neutral-400 hover:text-white hover:underline">
              Or analyze a public video / transcript without logging in ↓
            </a>
          </div>

          {/* RIGHT COLUMN: FLOATING CHARACTER WITH TILTEDCARD INTERACTION */}
          <div
            id="creator-character-stage"
            className="animate-character lg:col-span-5 xl:col-span-5 relative w-full flex items-center justify-center lg:justify-end xl:justify-center py-4 lg:py-0"
            aria-label="RetainAI Creator Character"
          >
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
    </main>
    <PublicAnalyzer />
    </>
  );
}
