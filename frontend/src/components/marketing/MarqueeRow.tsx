const SECOND_ROW_ITEMS = [
  "Frontend Engineer",
  "Backend Developer",
  "Product Manager",
  "Data Scientist",
  "DevOps Engineer",
  "ML Engineer",
  "Full-Stack Dev",
  "SDE-II",
];

type Props = {
  items: string[];
  direction?: "left" | "right";
  className?: string;
  /** When true, renders a second row going right with job titles */
  doubleRow?: boolean;
};

export function MarqueeRow({ items, direction = "left", className = "", doubleRow = false }: Props) {
  const doubled = [...items, ...items];
  const anim = direction === "left" ? "animate-marquee-left" : "animate-marquee-right";
  const secondDoubled = [...SECOND_ROW_ITEMS, ...SECOND_ROW_ITEMS];
  return (
    <div className={`relative overflow-hidden border-y border-border/60 bg-card/40 ${className}`}>
      <div className={`flex w-max gap-12 py-4 ${anim}`}>
        {doubled.map((item, i) => (
          <span key={i} className="whitespace-nowrap text-sm text-muted-foreground">
            {item}
          </span>
        ))}
      </div>
      {doubleRow && (
        <div className="flex w-max gap-12 pb-4 animate-marquee-right">
          {secondDoubled.map((item, i) => (
            <span key={i} className="whitespace-nowrap text-sm text-muted-foreground/70">
              {item}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

