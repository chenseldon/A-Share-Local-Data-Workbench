import { DatabaseZap } from "lucide-react";

interface EmptyStateProps {
  title: string;
  detail: string;
}

export function EmptyState({ title, detail }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <DatabaseZap aria-hidden="true" size={22} />
      <div>
        <h3>{title}</h3>
        <p>{detail}</p>
      </div>
    </div>
  );
}
