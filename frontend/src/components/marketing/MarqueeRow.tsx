type Props = {
  items: string[];
  direction?: "left" | "right";
  className?: string;
};

export function MarqueeRow({ items, direction = "left", className = "" }: Props) {
  const doubled = [...items, ...items];
  const anim = direction === "left" ? "animate-marquee-left" : "animate-marquee-right";
  return (
    <div className={`relative overflow-hidden border-y border-border/60 bg-card/40 py-4 ${className}`}>
      <div className={`flex w-max gap-12 ${anim}`}>
        {doubled.map((item, i) => (
          <span key={i} className="whitespace-nowrap text-sm text-muted-foreground">
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}
