export default function JobsLoading() {
  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div className="h-9 w-48 shimmer rounded-2xl" />
        <div className="flex gap-2">
          <div className="h-9 w-24 shimmer rounded-full" />
          <div className="h-9 w-32 shimmer rounded-full" />
        </div>
      </div>
      <div className="flex gap-2">
        <div className="h-10 flex-1 shimmer rounded-2xl" />
        <div className="h-10 w-24 shimmer rounded-full" />
      </div>
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-24 shimmer rounded-3xl" />
      ))}
    </div>
  );
}
