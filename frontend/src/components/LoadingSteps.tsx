import { Check, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

type LoadingStepsProps = {
  title: string;
  steps: string[];
  intervalMs?: number;
  className?: string;
};

export function LoadingSteps({ title, steps, intervalMs = 1100, className }: LoadingStepsProps) {
  const [active, setActive] = useState(0);

  useEffect(() => {
    setActive(0);
    const timer = window.setInterval(() => {
      setActive((current) => (current < steps.length - 1 ? current + 1 : current));
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [steps, intervalMs]);

  return (
    <div className={className ? `loading-steps ${className}` : "loading-steps"} role="status" aria-live="polite">
      <div className="loading-steps-head">
        <Loader2 className="spin" size={18} />
        <strong>{title}</strong>
      </div>
      <ol className="loading-steps-list">
        {steps.map((label, index) => {
          const state = index < active ? "done" : index === active ? "active" : "pending";
          return (
            <li key={label} className={`loading-step loading-step-${state}`}>
              <span className="loading-step-icon" aria-hidden="true">
                {state === "done" ? <Check size={12} strokeWidth={3} /> : null}
                {state === "active" ? <Loader2 className="spin" size={12} /> : null}
              </span>
              <span className="loading-step-label">{label}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
