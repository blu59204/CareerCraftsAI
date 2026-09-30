import { Bezel } from "@/components/vanguard/Bezel";
import { Skeleton } from "@/components/vanguard/Display";

/** Mirrors the dashboard: hero + harness aside, 8/4 command bento, stat strip, 7/5 activity row. */
export default function DashboardLoading() {
  return (
    <div
      role="status"
      aria-label="Loading dashboard"
      className="relative mx-auto w-full min-w-0 max-w-[1400px] space-y-6 pb-8 font-geist md:space-y-8 md:pb-12"
    >
      {/* Hero */}
      <div className="grid gap-6 pb-2 pt-2 md:pb-4 md:pt-4 lg:grid-cols-12 lg:items-end">
        <div className="space-y-6 lg:col-span-7 xl:col-span-8">
          <Skeleton className="h-6 w-32 rounded-full" />
          <div className="space-y-3">
            <Skeleton className="h-14 w-64 rounded-2xl md:h-20 md:w-96" />
            <Skeleton className="h-14 w-72 rounded-2xl md:h-20 md:w-[28rem]" />
          </div>
          <Skeleton className="h-4 w-80 max-w-full rounded-full" />
          <div className="flex flex-wrap gap-3 pt-2">
            <Skeleton className="h-14 w-44 rounded-full" />
            <Skeleton className="h-14 w-40 rounded-full" />
          </div>
        </div>
        <div className="lg:col-span-5 xl:col-span-4">
          <Bezel size="lg" coreClassName="space-y-5 p-6">
            <div className="flex items-center justify-between">
              <Skeleton className="h-4 w-28 rounded-full" />
              <Skeleton className="h-6 w-16 rounded-full" />
            </div>
            <div className="grid grid-cols-2 gap-5">
              <Skeleton className="h-14 rounded-2xl" />
              <Skeleton className="h-14 rounded-2xl" />
            </div>
          </Bezel>
        </div>
      </div>

      {/* Command bento */}
      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
        <Bezel size="lg" className="lg:col-span-8" coreClassName="space-y-5 p-4 sm:p-6">
          <Skeleton className="h-8 w-40 rounded-full" />
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <Skeleton className="h-10 w-10 shrink-0 rounded-xl" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3.5 w-2/5 rounded-full" />
                <Skeleton className="h-3 w-3/5 rounded-full" />
              </div>
              <Skeleton className="hidden h-9 w-24 rounded-full sm:block" />
            </div>
          ))}
          <div className="grid grid-cols-1 gap-3 pt-4 sm:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-36 rounded-[1.5rem]" />
            ))}
          </div>
        </Bezel>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:col-span-4 lg:grid-cols-1">
          <Bezel size="lg" coreClassName="space-y-6 p-6 md:p-7">
            <Skeleton className="h-8 w-36 rounded-full" />
            <div className="flex items-center gap-6">
              <Skeleton className="h-28 w-28 shrink-0 rounded-full" />
              <div className="flex-1 space-y-3">
                <Skeleton className="h-3 w-24 rounded-full" />
                <Skeleton className="h-7 w-16 rounded-xl" />
                <Skeleton className="h-1.5 w-full rounded-full" />
              </div>
            </div>
          </Bezel>
          <Bezel size="lg" coreClassName="space-y-5 p-6 md:p-7">
            <Skeleton className="h-8 w-32 rounded-full" />
            <Skeleton className="h-24 rounded-[1.25rem]" />
          </Bezel>
        </div>
        <Bezel size="lg" className="lg:col-span-12" coreClassName="grid grid-cols-2 gap-6 p-6 md:grid-cols-4 md:p-8">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="space-y-3">
              <Skeleton className="h-3 w-20 rounded-full" />
              <Skeleton className="h-10 w-16 rounded-xl md:h-12" />
            </div>
          ))}
        </Bezel>
      </div>

      {/* Activity + matches */}
      <div className="space-y-8 md:space-y-10">
        <div className="space-y-4">
          <Skeleton className="h-6 w-24 rounded-full" />
          <Skeleton className="h-8 w-72 max-w-full rounded-2xl" />
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <Bezel size="lg" className="lg:col-span-7" coreClassName="space-y-3 p-6 md:p-7">
            <Skeleton className="h-8 w-44 rounded-full" />
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-16 rounded-xl" />
            ))}
          </Bezel>
          <Bezel size="lg" className="lg:col-span-5" coreClassName="space-y-3 p-6 md:p-7">
            <Skeleton className="h-8 w-40 rounded-full" />
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-14 rounded-2xl" />
            ))}
          </Bezel>
        </div>
      </div>
      <span className="sr-only">Loading dashboard…</span>
    </div>
  );
}
