import { useEffect, useRef, type ReactNode } from "react";
import { useFinePointer } from "../../hooks/useFinePointer";
import { useReducedMotion } from "../../hooks/useReducedMotion";
import styles from "./CursorSpotlight.module.css";

interface CursorSpotlightProps {
  children: ReactNode;
  className?: string;
}

export function CursorSpotlight({ children, className = "" }: CursorSpotlightProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);
  const finePointer = useFinePointer();
  const reducedMotion = useReducedMotion();
  const enabled = finePointer && !reducedMotion;

  useEffect(() => {
    if (!enabled) return;

    const root = rootRef.current;
    const glow = glowRef.current;
    if (!root || !glow) return;

    let frame = 0;
    let targetX = 0;
    let targetY = 0;
    let currentX = 0;
    let currentY = 0;

    const render = () => {
      currentX += (targetX - currentX) * 0.12;
      currentY += (targetY - currentY) * 0.12;
      glow.style.transform = `translate3d(${currentX}px, ${currentY}px, 0)`;
      frame = window.requestAnimationFrame(render);
    };

    const onMove = (event: MouseEvent) => {
      const bounds = root.getBoundingClientRect();
      targetX = event.clientX - bounds.left - bounds.width / 2;
      targetY = event.clientY - bounds.top - bounds.height / 2;
    };

    frame = window.requestAnimationFrame(render);
    root.addEventListener("mousemove", onMove);
    return () => {
      cancelAnimationFrame(frame);
      root.removeEventListener("mousemove", onMove);
    };
  }, [enabled]);

  return (
    <div
      ref={rootRef}
      className={`${styles.root} ${enabled ? styles.enabled : ""} ${className}`.trim()}
    >
      {enabled ? <div ref={glowRef} className={styles.glow} aria-hidden="true" /> : null}
      {children}
    </div>
  );
}
