export default function ResumeLoading() {
  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div className="h-9 w-48 shimmer rounded-2xl" />
        <div className="flex gap-2">
          <div className="h-9 w-24 shimmer rounded-full" />
          <div className="h-9 w-28 shimmer rounded-full" />
          <div className="h-9 w-24 shimmer rounded-full" />
        </div>
      </div>
      <div className="h-10 w-80 shimmer rounded-full" />
      <div className="h-36 shimmer rounded-3xl" />
      <div className="grid gap-6 lg:grid-cols-[300px_1fr_320px]">
        <div className="space-y-4">
          <div className="h-48 shimmer rounded-3xl" />
          <div className="h-32 shimmer rounded-3xl" />
        </div>
        <div className="h-[500px] shimmer rounded-3xl" />
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-28 shimmer rounded-3xl" />
          ))}
        </div>
      </div>
    </div>
  );
}
