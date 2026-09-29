type Props = { suggestions: string[] };

/** Numbered, hairline-divided list of ATS recommendations. */
export function SuggestionsList({ suggestions }: Props) {
  return (
    <ol className="divide-y divide-foreground/[0.06] dark:divide-white/[0.07]">
      {suggestions.map((suggestion, index) => (
        <li key={`${index}-${suggestion}`} className="flex gap-4 py-3.5 first:pt-0 last:pb-0">
          <span aria-hidden="true" className="mt-0.5 font-geist-mono text-[11px] tabular-nums text-muted-foreground">
            {String(index + 1).padStart(2, "0")}
          </span>
          <p className="min-w-0 text-sm leading-6 text-foreground/90">{suggestion}</p>
        </li>
      ))}
    </ol>
  );
}
