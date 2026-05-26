export default function ApplicationsLoading() {
  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div className="h-9 w-48 shimmer rounded-2xl" />
        <div className="h-9 w-32 shimmer rounded-full" />
      </div>
      <div className="grid gap-4 md:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="space-y-3">
            <div className="h-8 shimmer rounded-2xl" />
            {Array.from({ length: 3 }).map((_, j) => (
              <div key={j} className="h-24 shimmer rounded-2xl" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
