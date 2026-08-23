import { useEffect, useState } from "react";

export function useFinePointer(): boolean {
  const [finePointer, setFinePointer] = useState(() => readFinePointerPreference());

  useEffect(() => {
    const media = window.matchMedia("(hover: hover) and (pointer: fine)");
    const sync = () => setFinePointer(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  return finePointer;
}

function readFinePointerPreference(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(hover: hover) and (pointer: fine)").matches;
}
