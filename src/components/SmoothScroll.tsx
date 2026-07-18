"use client";

import React, { useEffect, useRef } from "react";
import { ReactLenis, useLenis } from "lenis/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

function LenisGSAPSync() {
  const lenis = useLenis();
  const initialized = useRef(false);

  useEffect(() => {
    if (!lenis || initialized.current) return;
    initialized.current = true;

    // Sync Lenis scroll position → GSAP ScrollTrigger
    lenis.on("scroll", ScrollTrigger.update);

    // Use GSAP ticker to drive Lenis RAF loop
    const tickerCallback = (time: number) => {
      lenis.raf(time * 1000);
    };
    gsap.ticker.add(tickerCallback);
    gsap.ticker.lagSmoothing(0);

    return () => {
      gsap.ticker.remove(tickerCallback);
      lenis.off("scroll", ScrollTrigger.update);
    };
  }, [lenis]);

  return null;
}

interface SmoothScrollProps {
  children: React.ReactNode;
}

export default function SmoothScroll({ children }: SmoothScrollProps) {
  return (
    <ReactLenis root options={{ lerp: 0.08, duration: 1.2, smoothWheel: true, autoRaf: false }}>
      <LenisGSAPSync />
      {children}
    </ReactLenis>
  );
}
