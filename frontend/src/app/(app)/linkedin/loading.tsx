export default function LinkedInLoading() {
  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div className="h-9 w-48 shimmer rounded-2xl" />
        <div className="flex gap-2">
          <div className="h-9 w-32 shimmer rounded-full" />
          <div className="h-9 w-28 shimmer rounded-full" />
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 shimmer rounded-3xl" />
        ))}
      </div>
      <div className="flex gap-4">
        <div className="flex-[3] h-80 shimmer rounded-3xl" />
        <div className="flex-[2] h-80 shimmer rounded-3xl" />
      </div>
    </div>
  );
}
