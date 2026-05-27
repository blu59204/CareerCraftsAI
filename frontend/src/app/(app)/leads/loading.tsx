export default function LeadsLoading() {
  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between">
        <div className="h-9 w-52 shimmer rounded-2xl" />
        <div className="flex gap-2">
          <div className="h-9 w-36 shimmer rounded-full" />
          <div className="h-9 w-24 shimmer rounded-full" />
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-28 shimmer rounded-3xl" />
        ))}
      </div>
      <div className="space-y-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-16 shimmer rounded-3xl" />
        ))}
      </div>
    </div>
  );
}
