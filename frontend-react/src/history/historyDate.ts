export function formatHistoryDateTime(value: string, now = new Date()): string {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return "";

  const date = new Date(timestamp);
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
  const timeLabel = date.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });

  if (isSameLocalDate(date, now)) return `Today, ${timeLabel}`;
  if (isSameLocalDate(date, yesterday)) return `Yesterday, ${timeLabel}`;

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function isSameLocalDate(left: Date, right: Date): boolean {
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()
  );
}
