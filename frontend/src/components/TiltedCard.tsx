"use client";

import React, { useRef, useState } from "react";
import { motion, useMotionValue, useSpring } from "motion/react";

interface TiltedCardProps {
  imageSrc: string;
  altText?: string;
  captionText?: string;
  containerHeight?: string | number;
  containerWidth?: string | number;
  imageHeight?: string | number;
  imageWidth?: string | number;
  scaleOnHover?: number;
  rotateAmplitude?: number;
  showMobileWarning?: boolean;
  showTooltip?: boolean;
  displayOverlayContent?: boolean;
  className?: string;
}

const springValues = {
  damping: 30,
  stiffness: 100,
  mass: 2,
};

export default function TiltedCard({
  imageSrc,
  altText = "RetainAI Creator Character",
  captionText = "",
  containerHeight = "100%",
  containerWidth = "100%",
  imageHeight = "100%",
  imageWidth = "100%",
  scaleOnHover = 1.03,
  rotateAmplitude = 8,
  showMobileWarning = false,
  showTooltip = false,
  displayOverlayContent = false,
  className = "",
}: TiltedCardProps) {
  const ref = useRef<HTMLDivElement>(null);

  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const scale = useSpring(1, springValues);
  const rotateX = useSpring(0, springValues);
  const rotateY = useSpring(0, springValues);

  function handleMouse(e: React.MouseEvent<HTMLDivElement>) {
    if (!ref.current) return;

    const rect = ref.current.getBoundingClientRect();
    const offsetX = e.clientX - rect.left - rect.width / 2;
    const offsetY = e.clientY - rect.top - rect.height / 2;

    const rotationX = (offsetY / (rect.height / 2)) * -rotateAmplitude;
    const rotationY = (offsetX / (rect.width / 2)) * rotateAmplitude;

    rotateX.set(rotationX);
    rotateY.set(rotationY);
  }

  function handleMouseEnter() {
    scale.set(scaleOnHover);
  }

  function handleMouseLeave() {
    scale.set(1);
    rotateX.set(0);
    rotateY.set(0);
  }

  return (
    <figure
      ref={ref}
      className={`relative flex items-center justify-center select-none ${className}`}
      style={{
        height: containerHeight,
        width: containerWidth,
        perspective: "1000px",
        background: "transparent",
      }}
      onMouseMove={handleMouse}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <motion.div
        className="relative flex items-center justify-center will-change-transform"
        style={{
          width: imageWidth,
          height: imageHeight,
          transformStyle: "preserve-3d",
          rotateX,
          rotateY,
          scale,
          background: "transparent",
        }}
      >
        {/* Transparent Character Image */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imageSrc}
          alt={altText}
          className="w-full h-full object-contain pointer-events-none select-none drop-shadow-[0_20px_45px_rgba(0,0,0,0.85)]"
          style={{
            objectFit: "contain",
            maxHeight: "100%",
            maxWidth: "100%",
          }}
          loading="eager"
          decoding="async"
        />

        {displayOverlayContent && captionText && (
          <figcaption className="sr-only">{captionText}</figcaption>
        )}
      </motion.div>
    </figure>
  );
}
