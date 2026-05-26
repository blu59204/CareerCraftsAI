export default function AgentsLoading() {
  return (
    <div className="grid gap-6 lg:grid-cols-[220px_1fr_320px]">
      <div className="h-80 shimmer rounded-3xl" />
      <div className="h-[500px] shimmer rounded-3xl" />
      <div className="space-y-3">
        <div className="h-24 shimmer rounded-3xl" />
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-16 shimmer rounded-3xl" />
        ))}
      </div>
    </div>
  );
}
