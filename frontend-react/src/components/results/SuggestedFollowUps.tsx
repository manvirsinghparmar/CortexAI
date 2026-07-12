import { useEffect, useRef, useState } from "react";
import { CortexIcon } from "../shared/CortexIcon";
import styles from "./ResponseCard.module.css";

interface SuggestedFollowUpsProps {
  suggestions: string[];
  onSelect: (suggestion: string) => void | Promise<void>;
  disabled?: boolean;
}

export function SuggestedFollowUps({
  suggestions,
  onSelect,
  disabled = false,
}: SuggestedFollowUpsProps) {
  const [sentKey, setSentKey] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    };
  }, []);

  if (suggestions.length === 0) return null;

  const markSent = (key: string) => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    setSentKey(key);
    timerRef.current = window.setTimeout(() => {
      setSentKey(null);
      timerRef.current = null;
    }, 1700);
  };

  return (
    <div className={styles.followUpRow} aria-label="Suggested follow-ups">
      <div className={styles.followUpLabel}>
        <CortexIcon name="sparkle" size={13} strokeWidth={1.9} />
        <span>Suggested follow-ups</span>
      </div>
      <div className={styles.followUpChipList}>
        {suggestions.map((suggestion, index) => {
          const key = `f${index}`;
          const isSent = sentKey === key;
          return (
            <button
              key={`${key}-${suggestion}`}
              type="button"
              className={`${styles.followUpChip} ${isSent ? styles.followUpChipSent : ""}`}
              aria-label={`Ask follow-up: ${suggestion}`}
              title={suggestion}
              disabled={disabled || isSent}
              onClick={() => {
                markSent(key);
                void onSelect(suggestion);
              }}
            >
              <CortexIcon
                name={isSent ? "check" : "reply-return"}
                size={14}
                strokeWidth={isSent ? 2.1 : 1.85}
              />
              <span className={styles.followUpChipText}>{suggestion}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
