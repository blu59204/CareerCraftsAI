import { estimateSchema } from "@/lib/profile-contracts";

export function ScoreExplanation({ estimate }: { estimate: unknown }) {
  const parsed = estimateSchema.safeParse(estimate);
  if (!parsed.success) return null;
  const value = parsed.data;
  return (
    <details className="mt-4 text-sm">
      <summary>How this estimate was calculated</summary>
      <p className="mt-3 text-muted-foreground">{value.mode === "general" ? "General document compatibility" : "Compatibility with the target job"}. This estimate does not predict an employer’s decision.</p>
      <ul className="mt-3 space-y-1">
        {Object.entries(value.sub_scores).map(([name, score]) => <li key={name}>{name.replaceAll("_", " ")}: {score.applicable ? `${score.score}/100 · weight ${score.weight}` : "Not measured"}</li>)}
      </ul>
      <p className="mt-3 text-muted-foreground">{value.match_method}</p>
      <ul className="mt-3 space-y-2">{value.issues.map((issue, index) => <li key={index}><strong>{issue.severity} · {issue.section}</strong>: {issue.suggestion}</li>)}</ul>
    </details>
  );
}
