import { useEffect, useState } from "react";
import styles from "./ProviderLogo.module.css";

interface ProviderLogoProps {
  provider: string;
  logoUrl: string;
  color: string;
  size?: number;
  className?: string;
}

export function ProviderLogo({
  provider,
  logoUrl,
  color,
  size = 20,
  className = "",
}: ProviderLogoProps) {
  const [failed, setFailed] = useState(false);
  const dimensionStyle = {
    width: `${size}px`,
    height: `${size}px`,
    flexBasis: `${size}px`,
  };

  useEffect(() => {
    setFailed(false);
  }, [logoUrl]);

  if (!logoUrl || failed) {
    return (
      <span
        className={`${styles.fallback} ${className}`}
        style={{ ...dimensionStyle, backgroundColor: color }}
        data-provider-logo={provider || "model"}
        aria-hidden="true"
      >
        {(provider[0] ?? "M").toUpperCase()}
      </span>
    );
  }

  return (
    <img
      className={`${styles.logo} ${className}`}
      style={dimensionStyle}
      src={logoUrl}
      alt=""
      width={size}
      height={size}
      data-provider-logo={provider || "model"}
      loading="lazy"
      decoding="async"
      aria-hidden="true"
      onError={() => setFailed(true)}
    />
  );
}
