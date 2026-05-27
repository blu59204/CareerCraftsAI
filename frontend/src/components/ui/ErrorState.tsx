import { AlertTriangle } from "lucide-react";
import { LiquidGlassButton } from "./LiquidGlassButton";

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-3xl border border-danger/30 bg-danger/5 px-6 py-12 text-center">
      <AlertTriangle className="mb-3 h-6 w-6 text-danger" />
      <div className="text-sm text-foreground">{message}</div>
      {onRetry && (
        <div className="mt-4">
          <LiquidGlassButton tone="ghost" size="sm" onClick={onRetry}>
            Retry
          </LiquidGlassButton>
        </div>
      )}
    </div>
  );
}
