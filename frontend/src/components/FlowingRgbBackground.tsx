"use client";

import React from "react";

export default function FlowingRgbBackground() {
  return (
    <div
      className="pointer-events-none fixed inset-0 overflow-hidden select-none z-0"
      aria-hidden="true"
    >
      {/* Deep Near-Black Base */}
      <div className="absolute inset-0 bg-[#040405]" />

      {/* Atmospheric RGB Columns Container */}
      <div className="rgb-columns-container absolute inset-0">
        {/* Column 1: RED -> MAGENTA (Far Left) */}
        <div className="rgb-beam rgb-beam-1" />

        {/* Column 2: MAGENTA -> PURPLE (Mid Left) */}
        <div className="rgb-beam rgb-beam-2" />

        {/* Column 3: PURPLE -> BLUE (Center Left) */}
        <div className="rgb-beam rgb-beam-3" />

        {/* Column 4: BLUE -> CYAN -> RED (Center Right) */}
        <div className="rgb-beam rgb-beam-4" />

        {/* Column 5: CYAN -> PURPLE (Mid Right) */}
        <div className="rgb-beam rgb-beam-5" />

        {/* Column 6: MAGENTA -> RED (Far Right) */}
        <div className="rgb-beam rgb-beam-6" />
      </div>

      {/* Soft Center Darkening Layer (Preserves Card Contrast without Hiding Light) */}
      <div className="absolute inset-0 rgb-center-darkening" />

      {/* Cinematic Viewport Edge Vignette */}
      <div className="absolute inset-0 rgb-vignette" />

      {/* Subtle Analog Grain */}
      <div className="absolute inset-0 rgb-grain" />
    </div>
  );
}
