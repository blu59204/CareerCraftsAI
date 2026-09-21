type Props = { suggestions: string[] };

export function SuggestionsList({ suggestions }: Props) {
  return (
    <ul className="space-y-3">
      {suggestions.map((suggestion, index) => (
        <li key={`${index}-${suggestion}`} className="rounded-2xl border border-border bg-card/60 p-4 text-sm leading-relaxed">
          {suggestion}
        </li>
      ))}
    </ul>
  );
}
