export function StatusBadge({
  children,
  state = "neutral",
}: {
  children: React.ReactNode;
  state?: "good" | "warning" | "bad" | "neutral";
}) {
  return (
    <span className={`status-badge ${state}`}>
      <span className="status-dot" />
      {children}
    </span>
  );
}
