export function JsonLd({ data }: { data: Record<string, unknown> }) {
  return (
    <script
      type="application/ld+json"
      // JSON-LD is structured data, not executable code — a native <script>
      // tag is correct here (next/script is for loading real JS). Escaping
      // `<` prevents a malicious string in `data` from closing this tag early.
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, "\\u003c") }}
    />
  );
}
