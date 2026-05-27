export default function DashboardLoading() {
  return (
    <div className="space-y-8">
      <div className="h-9 w-56 shimmer rounded-2xl" />
      <div className="grid gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-28 shimmer rounded-3xl" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <div className="h-72 shimmer rounded-3xl" />
        <div className="space-y-3">
          <div className="h-20 shimmer rounded-3xl" />
          <div className="h-20 shimmer rounded-3xl" />
          <div className="h-20 shimmer rounded-3xl" />
        </div>
      </div>
    </div>
  );
}
