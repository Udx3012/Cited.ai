"use client";

import { useEffect } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

export function useGSAPAnimations() {
  useEffect(() => {
    // Small delay to ensure DOM is ready after hydration
    const ctx = gsap.context(() => {
      // ─── 1. PARALLAX BACKGROUND ORBS ────────────────────────────────
      gsap.utils.toArray<HTMLElement>("[data-gsap-orb]").forEach((orb) => {
        const speed = parseFloat(orb.dataset.gsapSpeed || "0.5");
        gsap.to(orb, {
          y: () => window.innerHeight * speed,
          ease: "none",
          scrollTrigger: {
            trigger: document.body,
            start: "top top",
            end: "bottom bottom",
            scrub: 1.5,
          },
        });
      });

      // ─── 2. HERO HEADING — CHARACTER STAGGER ────────────────────────
      const heroChars = gsap.utils.toArray<HTMLElement>("[data-gsap-hero-char]");
      if (heroChars.length > 0) {
        gsap.fromTo(
          heroChars,
          {
            opacity: 0,
            y: 40,
            rotateX: -90,
            scale: 0.8,
          },
          {
            opacity: 1,
            y: 0,
            rotateX: 0,
            scale: 1,
            stagger: 0.02,
            duration: 0.8,
            ease: "back.out(1.7)",
            delay: 0.3,
          }
        );
      }

      // ─── 3. HERO SUBTITLE — FADE SLIDE ──────────────────────────────
      const heroSub = document.querySelector("[data-gsap-hero-sub]");
      if (heroSub) {
        gsap.fromTo(
          heroSub,
          { opacity: 0, y: 30, filter: "blur(8px)" },
          { opacity: 1, y: 0, filter: "blur(0px)", duration: 1, ease: "power3.out", delay: 0.8 }
        );
      }

      // ─── 4. HERO CTA BUTTONS ───────────────────────────────────────
      const heroCtas = document.querySelector("[data-gsap-hero-ctas]");
      if (heroCtas) {
        gsap.fromTo(
          heroCtas,
          { opacity: 0, y: 20 },
          { opacity: 1, y: 0, duration: 0.8, ease: "power3.out", delay: 1.0 }
        );
      }

      // ─── 5. TRUST BANNER — ALTERNATING SLIDE IN ─────────────────────
      const trustItems = gsap.utils.toArray<HTMLElement>("[data-gsap-trust-item]");
      if (trustItems.length > 0) {
        gsap.fromTo(
          trustItems,
          { opacity: 0, x: (i: number) => (i % 2 === 0 ? -30 : 30) },
          {
            opacity: 1,
            x: 0,
            stagger: 0.08,
            duration: 0.6,
            ease: "power2.out",
            delay: 1.2,
          }
        );
      }

      // ─── 6. PLATFORM MOCKUP — 3D PERSPECTIVE TILT ──────────────────
      const mockup = document.querySelector("[data-gsap-mockup]") as HTMLElement;
      if (mockup) {
        gsap.fromTo(
          mockup,
          {
            opacity: 0,
            rotateX: 12,
            scale: 0.92,
            y: 80,
            transformPerspective: 1200,
            transformOrigin: "center bottom",
          },
          {
            opacity: 1,
            rotateX: 0,
            scale: 1,
            y: 0,
            duration: 1.2,
            ease: "power3.out",
            scrollTrigger: {
              trigger: mockup,
              start: "top 85%",
              end: "top 30%",
              scrub: 1,
            },
          }
        );

        // Floating shadow underneath
        const mockupShadow = document.querySelector("[data-gsap-mockup-shadow]");
        if (mockupShadow) {
          gsap.fromTo(
            mockupShadow,
            { opacity: 0, scaleX: 0.7 },
            {
              opacity: 1,
              scaleX: 1,
              scrollTrigger: {
                trigger: mockup,
                start: "top 85%",
                end: "top 30%",
                scrub: 1,
              },
            }
          );
        }
      }

      // ─── 7. SECTION LABELS — LINE GROW + TEXT FADE ──────────────────
      gsap.utils.toArray<HTMLElement>("[data-gsap-section-label]").forEach((label) => {
        const line = label.querySelector("[data-gsap-label-line]");
        const text = label.querySelector("[data-gsap-label-text]");

        const tl = gsap.timeline({
          scrollTrigger: {
            trigger: label,
            start: "top 85%",
            toggleActions: "play none none none",
          },
        });

        if (line) {
          tl.fromTo(line, { scaleX: 0 }, { scaleX: 1, duration: 0.6, ease: "power2.out" });
        }
        if (text) {
          tl.fromTo(text, { opacity: 0, x: -20 }, { opacity: 1, x: 0, duration: 0.5, ease: "power2.out" }, "-=0.3");
        }
      });

      // ─── 8. SECTION HEADINGS — REVEAL SLIDE UP ─────────────────────
      gsap.utils.toArray<HTMLElement>("[data-gsap-heading]").forEach((heading) => {
        gsap.fromTo(
          heading,
          { opacity: 0, y: 50, clipPath: "inset(100% 0% 0% 0%)" },
          {
            opacity: 1,
            y: 0,
            clipPath: "inset(0% 0% 0% 0%)",
            duration: 1,
            ease: "power3.out",
            scrollTrigger: {
              trigger: heading,
              start: "top 85%",
              toggleActions: "play none none none",
            },
          }
        );
      });

      // ─── 9. CAPABILITIES CARDS — STAGGER SCALE + ROTATE ────────────
      const capCards = gsap.utils.toArray<HTMLElement>("[data-gsap-cap-card]");
      if (capCards.length > 0) {
        gsap.fromTo(
          capCards,
          {
            opacity: 0,
            scale: 0.85,
            y: 60,
            rotate: -2,
          },
          {
            opacity: 1,
            scale: 1,
            y: 0,
            rotate: 0,
            stagger: 0.08,
            duration: 0.7,
            ease: "back.out(1.4)",
            scrollTrigger: {
              trigger: capCards[0],
              start: "top 85%",
              toggleActions: "play none none none",
            },
          }
        );
      }

      // ─── 10. ARCHITECTURE STEPS — CASCADE WATERFALL FROM RIGHT ─────
      const archSteps = gsap.utils.toArray<HTMLElement>("[data-gsap-arch-step]");
      if (archSteps.length > 0) {
        gsap.fromTo(
          archSteps,
          {
            opacity: 0,
            x: 80,
            scale: 0.95,
          },
          {
            opacity: 1,
            x: 0,
            scale: 1,
            stagger: 0.1,
            duration: 0.6,
            ease: "power3.out",
            scrollTrigger: {
              trigger: archSteps[0],
              start: "top 85%",
              toggleActions: "play none none none",
            },
          }
        );
      }

      // ─── 11. WORKFLOW CARDS — STAGGER RISE WITH SCALE ──────────────
      const wfCards = gsap.utils.toArray<HTMLElement>("[data-gsap-wf-card]");
      if (wfCards.length > 0) {
        gsap.fromTo(
          wfCards,
          {
            opacity: 0,
            y: 80,
            scale: 0.9,
          },
          {
            opacity: 1,
            y: 0,
            scale: 1,
            stagger: 0.15,
            duration: 0.8,
            ease: "power3.out",
            scrollTrigger: {
              trigger: wfCards[0],
              start: "top 85%",
              toggleActions: "play none none none",
            },
          }
        );
      }

      // ─── 12. STACK PILLS — RADIAL BURST FROM CENTER ────────────────
      const stackPills = gsap.utils.toArray<HTMLElement>("[data-gsap-stack-pill]");
      if (stackPills.length > 0) {
        gsap.fromTo(
          stackPills,
          {
            opacity: 0,
            scale: 0,
          },
          {
            opacity: 1,
            scale: 1,
            stagger: {
              each: 0.06,
              from: "center",
            },
            duration: 0.5,
            ease: "back.out(2)",
            scrollTrigger: {
              trigger: stackPills[0],
              start: "top 85%",
              toggleActions: "play none none none",
            },
          }
        );
      }

      // ─── 13. CTA SECTION — PARALLAX + GLOW PULSE ──────────────────
      const ctaSection = document.querySelector("[data-gsap-cta]") as HTMLElement;
      if (ctaSection) {
        // Slower parallax
        gsap.fromTo(
          ctaSection,
          { y: 60 },
          {
            y: -30,
            ease: "none",
            scrollTrigger: {
              trigger: ctaSection,
              start: "top bottom",
              end: "bottom top",
              scrub: 2,
            },
          }
        );

        // Border glow pulse
        const ctaGlow = ctaSection.querySelector("[data-gsap-cta-glow]");
        if (ctaGlow) {
          gsap.fromTo(
            ctaGlow,
            { opacity: 0, scale: 0.95 },
            {
              opacity: 1,
              scale: 1,
              duration: 1.5,
              ease: "power2.out",
              scrollTrigger: {
                trigger: ctaSection,
                start: "top 70%",
                toggleActions: "play none none none",
              },
            }
          );
        }
      }

      // ─── 14. FOOTER — GENTLE RISE ──────────────────────────────────
      const footer = document.querySelector("[data-gsap-footer]");
      if (footer) {
        gsap.fromTo(
          footer,
          { opacity: 0, y: 40 },
          {
            opacity: 1,
            y: 0,
            duration: 0.8,
            ease: "power2.out",
            scrollTrigger: {
              trigger: footer,
              start: "top 95%",
              toggleActions: "play none none none",
            },
          }
        );
      }

      // ─── 15. CURSOR GLOW FOLLOWER ──────────────────────────────────
      const cursorGlow = document.querySelector("[data-gsap-cursor-glow]") as HTMLElement;
      if (cursorGlow) {
        const moveCursor = (e: MouseEvent) => {
          gsap.to(cursorGlow, {
            x: e.clientX,
            y: e.clientY,
            duration: 0.8,
            ease: "power2.out",
          });
        };
        window.addEventListener("mousemove", moveCursor);
      }
    });

    return () => {
      ctx.revert();
    };
  }, []);
}
