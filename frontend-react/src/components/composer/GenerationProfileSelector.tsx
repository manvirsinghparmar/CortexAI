import type { GenerationProfile } from "../../types";
import styles from "./PromptComposer.module.css";

const OPTIONS: Array<{ value: GenerationProfile; label: string; detail: string }> = [
  { value: "quick", label: "Quick", detail: "1K - shortest" },
  { value: "balanced", label: "Balanced", detail: "4K - recommended" },
  { value: "deep", label: "Deep", detail: "12K - more credits" },
  { value: "extended", label: "Extended", detail: "32K - highest room" },
];

export function GenerationProfileSelector({
  value,
  onChange,
  disabled = false,
  estimateLabel,
}: {
  value: GenerationProfile;
  onChange: (value: GenerationProfile) => void;
  disabled?: boolean;
  estimateLabel?: string;
}) {
  return (
    <label className={styles.depthControl}>
      <span>Answer depth</span>
      <select
        aria-label="Answer depth"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value as GenerationProfile)}
      >
        {OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}: {option.detail}
          </option>
        ))}
      </select>
      {estimateLabel && <small>{estimateLabel}</small>}
    </label>
  );
}
