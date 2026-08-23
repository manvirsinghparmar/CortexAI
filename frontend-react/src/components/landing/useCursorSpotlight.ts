import { useEffect, useRef } from "react";

export function useCursorSpotlight() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Only enable cursor tracking on fine-pointer devices with hover capability
    if (typeof window === "undefined" || !window.matchMedia) return;
    const canHover = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
    if (!canHover) return;

    const container = containerRef.current;
    if (!container) return;

    let rafId: number | null = null;

    const handleMouseMove = (e: MouseEvent) => {
      if (rafId) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        const rect = container.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        container.style.setProperty("--mouse-x", `${x}px`);
        container.style.setProperty("--mouse-y", `${y}px`);
      });
    };

    container.addEventListener("mousemove", handleMouseMove, { passive: true });

    return () => {
      if (rafId) cancelAnimationFrame(rafId);
      container.removeEventListener("mousemove", handleMouseMove);
    };
  }, []);

  return containerRef;
}
