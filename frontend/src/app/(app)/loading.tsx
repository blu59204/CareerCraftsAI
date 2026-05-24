export default function AppLoading() {
  return (
    <div className="space-y-6">
      <div className="h-10 w-48 shimmer rounded-2xl" />
      <div className="grid gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-28 shimmer rounded-3xl" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="h-64 shimmer rounded-3xl" />
        <div className="h-64 shimmer rounded-3xl" />
      </div>
    </div>
  );
}
