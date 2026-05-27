export default function EmailLoading() {
  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div className="h-9 w-44 shimmer rounded-2xl" />
        <div className="h-9 w-32 shimmer rounded-full" />
      </div>
      <div className="grid gap-6 lg:grid-cols-[280px_1fr_300px]">
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-16 shimmer rounded-2xl" />
          ))}
        </div>
        <div className="h-[500px] shimmer rounded-3xl" />
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 shimmer rounded-2xl" />
          ))}
        </div>
      </div>
    </div>
  );
}
