interface FeatureChipsProps {
  smartMode: boolean;
  researchMode: boolean;
  optimizeMode: boolean;
  onSmartToggle: (v: boolean) => void;
  onResearchToggle: (v: boolean) => void;
  onOptimizeToggle: (v: boolean) => void;
}

export function FeatureChips({
  smartMode,
  researchMode,
  optimizeMode,
  onSmartToggle,
  onResearchToggle,
  onOptimizeToggle,
}: FeatureChipsProps) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <Chip active={smartMode} icon="✨" label="Smart" tooltip="Gets you the best answer automatically" onToggle={onSmartToggle} ariaLabel="Smart routing" />
      <Chip active={researchMode} icon="🌐" label="Web" tooltip="Uses latest information from the web" onToggle={onResearchToggle} ariaLabel="Research mode" />
      <Chip active={optimizeMode} icon="✎" label="Improve" tooltip="Helps you ask better for better results" onToggle={onOptimizeToggle} ariaLabel="Prompt optimization" />
    </div>
  );
}

interface ChipProps {
  active: boolean;
  icon: string;
  label: string;
  tooltip: string;
  onToggle: (v: boolean) => void;
  ariaLabel: string;
}

function Chip({ active, icon, label, tooltip, onToggle, ariaLabel }: ChipProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={active}
      aria-label={ariaLabel}
      title={tooltip}
      onClick={() => onToggle(!active)}
      className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-all border ${
        active
          ? "bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 border-zinc-900 dark:border-zinc-100"
          : "bg-transparent text-zinc-500 dark:text-zinc-400 border-zinc-200 dark:border-zinc-700 hover:border-zinc-400 dark:hover:border-zinc-500"
      }`}
    >
      <span aria-hidden="true">{icon}</span>
      <span>{label}</span>
    </button>
  );
}
