import { Bezel } from "@/components/vanguard/Bezel";
import { Skeleton } from "@/components/vanguard/Display";

/** Mirrors the Leads directory: hero + stat strip aside, filter island, contact rows + lg detail panel. */
export default function LeadsLoading() {
  return (
    <div className="relative mx-auto w-full min-w-0 max-w-[1400px] space-y-6 pb-8 font-geist md:space-y-8 md:pb-12" aria-busy="true" aria-label="Loading recruiter contacts">
      {/* Hero */}
      <div className="grid gap-6 pb-2 pt-2 md:pb-4 md:pt-4 lg:grid-cols-12 lg:items-end">
        <div className="lg:col-span-7 xl:col-span-8">
          <Skeleton className="h-6 w-28 rounded-full" />
          <Skeleton className="mt-6 h-12 w-full max-w-[26rem] sm:h-16" />
          <Skeleton className="mt-3 h-12 w-3/4 max-w-[22rem] sm:h-16" />
          <Skeleton className="mt-6 h-4 w-full max-w-[34rem] rounded-full" />
          <Skeleton className="mt-2 h-4 w-2/3 max-w-[24rem] rounded-full" />
          <div className="mt-8 flex flex-wrap gap-3">
            <Skeleton className="h-14 w-36 rounded-full" />
            <Skeleton className="h-14 w-40 rounded-full" />
          </div>
        </div>
        <div className="lg:col-span-5 xl:col-span-4">
          <Bezel coreClassName="grid grid-cols-2 gap-6 p-6 md:grid-cols-3 md:p-7">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="space-y-3">
                <Skeleton className="h-3 w-16 rounded-full" />
                <Skeleton className="h-10 w-12 md:h-12" />
              </div>
            ))}
          </Bezel>
        </div>
      </div>

      <div className="space-y-8 md:space-y-10">
        {/* Filter island */}
        <Bezel size="md" coreClassName="flex flex-col gap-2 p-2 md:flex-row md:items-center md:gap-3">
          <Skeleton className="h-12 w-full rounded-2xl md:max-w-md" />
          <Skeleton className="h-10 w-full rounded-full md:ml-auto md:w-80" />
        </Bezel>

        {/* Directory + detail */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:items-start">
          <div className="space-y-3 lg:col-span-8">
            <Skeleton className="mb-4 h-8 w-40 rounded-full" />
            {Array.from({ length: 6 }).map((_, i) => (
              <Bezel key={i} size="md" coreClassName="flex items-center gap-4 p-4 md:py-3 md:pl-3">
                <Skeleton className="h-11 w-11 shrink-0 rounded-[0.9rem]" />
                <div className="min-w-0 flex-1 space-y-2">
                  <Skeleton className="h-3.5 w-36 rounded-full" />
                  <Skeleton className="h-3 w-24 rounded-full" />
                </div>
                <Skeleton className="hidden h-3 w-40 rounded-full md:block" />
                <Skeleton className="hidden h-6 w-20 rounded-full sm:block" />
                <Skeleton className="h-9 w-28 rounded-full" />
              </Bezel>
            ))}
          </div>
          <div className="hidden lg:col-span-4 lg:block">
            <Bezel tone="muted" coreClassName="flex min-h-[26rem] flex-col items-center justify-center gap-5 p-6">
              <Skeleton className="h-14 w-14 rounded-full" />
              <Skeleton className="h-4 w-36 rounded-full" />
              <Skeleton className="h-3 w-52 rounded-full" />
            </Bezel>
          </div>
        </div>
      </div>
    </div>
  );
}
