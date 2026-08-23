import { useEffect, useState } from "react";
import { useReducedMotion } from "../../hooks/useReducedMotion";
import styles from "./ScrollProgress.module.css";

export function ScrollProgress() {
  const reducedMotion = useReducedMotion();
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (reducedMotion) return;

    let frame = 0;
    const update = () => {
      const scrollTop = window.scrollY;
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
      const next = maxScroll > 0 ? Math.min(1, scrollTop / maxScroll) : 0;
      setProgress(next);
    };

    const onScroll = () => {
      cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(update);
    };

    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [reducedMotion]);

  if (reducedMotion) return null;

  return (
    <div className={styles.track} aria-hidden="true">
      <div className={styles.bar} style={{ transform: `scaleX(${progress})` }} />
    </div>
  );
}
