"use client";

import { Check, X } from "lucide-react";

export type Suggestion = { id: string; original: string; suggestion: string };

type Props = {
  suggestions: Suggestion[];
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
};

export function SuggestionsList({ suggestions, onAccept, onReject }: Props) {
  return (
    <div className="space-y-3">
      {suggestions.map((s) => (
        <div key={s.id} className="rounded-3xl border border-border bg-card/60 p-4">
          <div className="text-xs text-muted-foreground">Original</div>
          <p className="mt-1 text-sm line-through opacity-70">{s.original}</p>
          <div className="mt-3 text-xs text-primary">Suggested</div>
          <p className="mt-1 text-sm">{s.suggestion}</p>
          <div className="mt-4 flex gap-2">
            <button onClick={() => onAccept(s.id)} className="inline-flex items-center gap-1 rounded-full bg-success/15 px-3 py-1.5 text-xs text-success hover:bg-success/25">
              <Check className="h-3 w-3" /> Accept
            </button>
            <button onClick={() => onReject(s.id)} className="inline-flex items-center gap-1 rounded-full bg-muted px-3 py-1.5 text-xs text-muted-foreground hover:bg-card">
              <X className="h-3 w-3" /> Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
