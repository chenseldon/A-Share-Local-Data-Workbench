import { DatabaseZap } from "lucide-react";
import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  detail: string;
  action?: ReactNode;
}

export function EmptyState({ title, detail, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <DatabaseZap aria-hidden="true" size={22} />
      <div>
        <h3>{title}</h3>
        <p>{detail}</p>
        {action && <div className="empty-state-action">{action}</div>}
      </div>
    </div>
  );
}
