export default function InterviewPrepLoading() {
  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div className="h-9 w-52 shimmer rounded-2xl" />
        <div className="flex gap-2">
          <div className="h-9 w-36 shimmer rounded-full" />
          <div className="h-9 w-32 shimmer rounded-full" />
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-14 shimmer rounded-2xl" />
          ))}
        </div>
        <div className="h-[480px] shimmer rounded-3xl" />
      </div>
    </div>
  );
}
