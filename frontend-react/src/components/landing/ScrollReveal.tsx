import type {
  ReactNode,
  CSSProperties,
  HTMLAttributes,
} from "react";
import { useScrollReveal } from "./useScrollReveal";
import styles from "./ScrollReveal.module.css";

interface ScrollRevealProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  variant?: "fade-up" | "fade-in" | "slide-left" | "slide-right" | "zoom-in";
  delay?: number;
  threshold?: number;
  rootMargin?: string;
  className?: string;
  style?: CSSProperties;
  once?: boolean;
}

export function ScrollReveal({
  children,
  variant = "fade-up",
  delay = 0,
  threshold = 0.12,
  rootMargin = "0px 0px -40px 0px",
  once = true,
  className = "",
  style,
  ...rest
}: ScrollRevealProps) {
  const { ref, isVisible } = useScrollReveal({ threshold, rootMargin, once });

  const variantClass = styles[variant] || styles.fadeUp;
  const combinedClass = `${styles.revealBase} ${variantClass} ${
    isVisible ? styles.visible : ""
  } ${className}`.trim();

  const inlineStyle: CSSProperties = {
    ...style,
    transitionDelay: `${delay}ms`,
  };

  return (
    <div ref={ref} className={combinedClass} style={inlineStyle} {...rest}>
      {children}
    </div>
  );
}
