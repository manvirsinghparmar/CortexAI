import { useRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { useFinePointer } from "../../hooks/useFinePointer";
import { useReducedMotion } from "../../hooks/useReducedMotion";
import styles from "./MagneticButton.module.css";

interface MagneticButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost";
}

export function MagneticButton({
  children,
  className = "",
  variant = "primary",
  onMouseMove,
  onMouseLeave,
  ...props
}: MagneticButtonProps) {
  const buttonRef = useRef<HTMLButtonElement>(null);
  const finePointer = useFinePointer();
  const reducedMotion = useReducedMotion();
  const magnetic = finePointer && !reducedMotion;

  const handleMove = (event: React.MouseEvent<HTMLButtonElement>) => {
    onMouseMove?.(event);
    if (!magnetic || !buttonRef.current) return;

    const rect = buttonRef.current.getBoundingClientRect();
    const offsetX = (event.clientX - rect.left - rect.width / 2) * 0.12;
    const offsetY = (event.clientY - rect.top - rect.height / 2) * 0.18;
    buttonRef.current.style.transform = `translate3d(${offsetX}px, ${offsetY}px, 0)`;
  };

  const handleLeave = (event: React.MouseEvent<HTMLButtonElement>) => {
    onMouseLeave?.(event);
    if (!buttonRef.current) return;
    buttonRef.current.style.transform = "";
  };

  return (
    <button
      ref={buttonRef}
      {...props}
      className={`${styles.button} ${styles[variant]} ${className}`.trim()}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
    >
      {children}
    </button>
  );
}
