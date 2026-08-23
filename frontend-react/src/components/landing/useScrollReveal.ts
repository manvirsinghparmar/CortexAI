import { useEffect, useRef, useState } from "react";

export function useScrollReveal(options: {
  threshold?: number;
  rootMargin?: string;
  once?: boolean;
} = {}) {
  const { threshold = 0.15, rootMargin = "0px 0px -50px 0px", once = true } = options;
  const elementRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(() => {
    // If IntersectionObserver is unavailable (e.g., SSR or jsdom test), default to visible
    return typeof window === "undefined" || !("IntersectionObserver" in window);
  });

  useEffect(() => {
    if (typeof window === "undefined" || !("IntersectionObserver" in window)) {
      setIsVisible(true);
      return;
    }

    const element = elementRef.current;
    if (!element) return;

    // If user prefers reduced motion, show immediately
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setIsVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsVisible(true);
            if (once) {
              observer.unobserve(entry.target);
            }
          } else if (!once) {
            setIsVisible(false);
          }
        });
      },
      { threshold, rootMargin },
    );

    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, [threshold, rootMargin, once]);

  return { ref: elementRef, isVisible };
}
