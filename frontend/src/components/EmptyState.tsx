import { Radio } from "lucide-react";
export function EmptyState({
  title = "Waiting for telemetry",
  children,
}: {
  title?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Radio size={24} />
      </div>
      <h3>{title}</h3>
      <p>
        {children ||
          "Connect your configured ESP32 or start the labelled simulator to see live measurements."}
      </p>
    </div>
  );
}
