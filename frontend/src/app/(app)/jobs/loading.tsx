import { Bezel } from "@/components/vanguard/Bezel";
import { Skeleton } from "@/components/vanguard/Display";
import { Screen } from "@/components/vanguard/Screen";

/** Mirrors the Jobs layout: hero + search island + agent console, then featured match / rows / detail panel. */
export default function JobsLoading() {
  return (
    <Screen>
      <div aria-busy="true" aria-label="Loading jobs" className="grid gap-10 pb-12 pt-6 md:pb-20 md:pt-14 lg:grid-cols-12 lg:items-start">
        <div className="min-w-0 space-y-6 lg:col-span-7 xl:col-span-8">
          <Skeleton className="h-6 w-36 rounded-full" />
          <div className="space-y-3">
            <Skeleton className="h-12 w-full max-w-[34rem] rounded-2xl md:h-16" />
            <Skeleton className="h-12 w-2/3 max-w-[22rem] rounded-2xl md:h-16" />
          </div>
          <Skeleton className="h-4 w-full max-w-[36rem] rounded-lg" />
          <Bezel coreClassName="flex flex-col gap-2 p-1.5 md:flex-row md:items-center">
            <Skeleton className="h-14 flex-1 rounded-[1.25rem]" />
            <Skeleton className="h-14 w-full rounded-[1.25rem] md:w-56" />
            <Skeleton className="h-14 w-full rounded-full md:w-36" />
          </Bezel>
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-20 rounded-full" />
            ))}
          </div>
        </div>
        <div className="min-w-0 lg:col-span-5 xl:col-span-4">
          <Bezel coreClassName="space-y-6 p-6">
            <div className="flex items-center justify-between">
              <Skeleton className="h-3 w-28 rounded-md" />
              <Skeleton className="h-6 w-16 rounded-full" />
            </div>
            <Skeleton className="h-10 w-full rounded-xl" />
            <div className="grid grid-cols-3 gap-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="space-y-2">
                  <Skeleton className="h-2.5 w-14 rounded-md" />
                  <Skeleton className="h-8 w-12 rounded-lg" />
                </div>
              ))}
            </div>
          </Bezel>
        </div>
      </div>

      <div aria-hidden className="space-y-8 md:space-y-10">
        <div className="space-y-4">
          <Skeleton className="h-6 w-28 rounded-full" />
          <Skeleton className="h-8 w-72 rounded-xl" />
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="space-y-4 lg:col-span-7">
            <Bezel tone="primary" coreClassName="space-y-6 p-6 md:p-8">
              <Skeleton className="h-6 w-28 rounded-full" />
              <Skeleton className="h-10 w-3/4 rounded-xl" />
              <Skeleton className="h-4 w-1/2 rounded-lg" />
              <Skeleton className="h-1.5 w-full rounded-full" />
              <div className="flex gap-2">
                <Skeleton className="h-11 w-24 rounded-full" />
                <Skeleton className="h-11 w-28 rounded-full" />
              </div>
            </Bezel>
            {Array.from({ length: 3 }).map((_, i) => (
              <Bezel key={i} size="md" coreClassName="flex items-center gap-4 p-4 md:p-5">
                <Skeleton className="h-14 w-14 shrink-0 rounded-2xl" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-3 w-24 rounded-md" />
                  <Skeleton className="h-4 w-2/3 rounded-md" />
                </div>
                <Skeleton className="hidden h-9 w-40 rounded-full md:block" />
              </Bezel>
            ))}
          </div>
          <div className="hidden lg:col-span-5 lg:block">
            <Bezel coreClassName="space-y-5 p-6">
              <Skeleton className="h-4 w-24 rounded-md" />
              <Skeleton className="h-8 w-3/4 rounded-xl" />
              <Skeleton className="h-64 w-full" />
              <Skeleton className="h-11 w-full rounded-full" />
            </Bezel>
          </div>
        </div>
      </div>
    </Screen>
  );
}
