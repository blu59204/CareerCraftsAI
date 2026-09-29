import { Bezel } from "@/components/vanguard/Bezel";
import { Skeleton } from "@/components/vanguard/Display";

/**
 * Server-safe skeletons for the merged Interview screen (no hooks, no client
 * imports) — used by the route `loading.tsx` files and the Suspense fallback.
 * Mirrors the Prep plan layout: target bar, 8/4 bento, 7/5 bento.
 */
export function InterviewBodySkeleton() {
  return (
    <div className="space-y-6" aria-hidden>
      <Bezel coreClassName="grid grid-cols-1 gap-4 p-4 md:grid-cols-2 md:p-5 lg:grid-cols-12 lg:items-end">
        <div className="space-y-2 lg:col-span-4">
          <Skeleton className="h-3 w-16 rounded-full" />
          <Skeleton className="h-[52px] rounded-2xl" />
        </div>
        <div className="space-y-2 lg:col-span-4">
          <Skeleton className="h-3 w-12 rounded-full" />
          <Skeleton className="h-[52px] rounded-2xl" />
        </div>
        <div className="flex md:col-span-2 lg:col-span-4 lg:justify-end">
          <Skeleton className="h-11 w-full rounded-full lg:w-52" />
        </div>
      </Bezel>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <Bezel className="lg:col-span-8" coreClassName="space-y-5 p-5 md:p-7">
          <div className="flex items-center justify-between">
            <Skeleton className="h-8 w-48 rounded-full" />
            <Skeleton className="h-6 w-20 rounded-full" />
          </div>
          <Skeleton className="h-10 w-full max-w-md rounded-full" />
          <div className="space-y-6 pt-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="space-y-3">
                <Skeleton className="h-4 w-32 rounded-full" />
                <Skeleton className="h-5 w-full rounded-full" />
                <Skeleton className="h-5 w-2/3 rounded-full" />
              </div>
            ))}
          </div>
        </Bezel>
        <div className="space-y-6 lg:col-span-4">
          <Bezel tone="primary" coreClassName="space-y-4 p-6">
            <Skeleton className="h-8 w-44 rounded-full" />
            <Skeleton className="h-4 w-full rounded-full" />
            <Skeleton className="h-4 w-3/4 rounded-full" />
            <Skeleton className="h-11 w-full rounded-full" />
          </Bezel>
          <Bezel coreClassName="space-y-4 p-6">
            <Skeleton className="h-8 w-36 rounded-full" />
            <div className="flex items-center gap-5">
              <Skeleton className="h-24 w-24 rounded-full" />
              <Skeleton className="h-6 w-20 rounded-full" />
            </div>
          </Bezel>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <Bezel className="lg:col-span-7" coreClassName="grid grid-cols-1 gap-3 p-5 sm:grid-cols-2 md:p-7">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </Bezel>
        <Bezel className="lg:col-span-5" coreClassName="space-y-3 p-6">
          <Skeleton className="h-8 w-40 rounded-full" />
          <Skeleton className="h-4 w-full rounded-full" />
          <Skeleton className="h-4 w-5/6 rounded-full" />
        </Bezel>
      </div>
    </div>
  );
}

/** Full-route skeleton: static hero block + body (loading.tsx). */
export function InterviewLoadingSkeleton() {
  return (
    <div className="relative mx-auto w-full max-w-[1400px] pb-24 font-geist md:pb-40" aria-busy="true" aria-label="Loading interview workspace">
      <div className="grid gap-10 pb-8 pt-6 md:pb-10 md:pt-14 lg:grid-cols-12 lg:items-end">
        <div className="space-y-6 lg:col-span-7 xl:col-span-8">
          <Skeleton className="h-6 w-32 rounded-full" />
          <Skeleton className="h-14 w-full max-w-lg rounded-2xl md:h-16" />
          <Skeleton className="h-14 w-full max-w-md rounded-2xl md:h-16" />
          <Skeleton className="h-4 w-full max-w-xl rounded-full" />
          <Skeleton className="h-11 w-72 rounded-full" />
        </div>
        <div className="hidden lg:col-span-5 lg:block xl:col-span-4">
          <Bezel coreClassName="space-y-4 p-6">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full rounded-2xl" />
            ))}
          </Bezel>
        </div>
      </div>
      <InterviewBodySkeleton />
    </div>
  );
}
