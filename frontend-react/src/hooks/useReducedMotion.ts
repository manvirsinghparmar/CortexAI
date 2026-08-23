import { useEffect, useState } from "react";

export function useReducedMotion(): boolean {
  const [reducedMotion, setReducedMotion] = useState(() => readReducedMotionPreference());

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReducedMotion(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  return reducedMotion;
}

function readReducedMotionPreference(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
