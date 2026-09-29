import { Bezel } from "@/components/vanguard/Bezel";
import { Hairline, Skeleton } from "@/components/vanguard/Display";

/**
 * Mirrors the email workspace: hero + meta strip, then the mail-client
 * composition — slim mailbox rail, dominant composer, assistant rail.
 */
export default function EmailLoading() {
  return (
    <div
      role="status"
      aria-label="Loading outreach workspace"
      className="relative mx-auto w-full max-w-[1400px] space-y-12 pb-24 font-geist md:space-y-10 md:pb-40"
    >
      {/* Hero */}
      <div className="grid gap-10 pb-12 pt-6 md:pb-20 md:pt-14 lg:grid-cols-12 lg:items-end">
        <div className="space-y-6 lg:col-span-7 xl:col-span-8">
          <Skeleton className="h-6 w-28 rounded-full" />
          <div className="space-y-3">
            <Skeleton className="h-12 w-full max-w-[34rem] rounded-2xl md:h-16" />
            <Skeleton className="h-12 w-2/3 max-w-[22rem] rounded-2xl md:h-16" />
          </div>
          <Skeleton className="h-4 w-full max-w-[30rem] rounded-full" />
          <div className="flex flex-wrap gap-3 pt-2">
            <Skeleton className="h-11 w-40 rounded-full" />
            <Skeleton className="h-11 w-32 rounded-full" />
          </div>
        </div>
        <div className="lg:col-span-5 xl:col-span-4">
          <Skeleton className="h-[6.5rem] w-full rounded-[1.5rem]" />
        </div>
      </div>

      {/* Workspace */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Mailbox rail */}
        <Bezel size="md" className="min-w-0 lg:col-span-4 xl:col-span-3" coreClassName="flex flex-col gap-4 p-4">
          <div className="space-y-2 px-1 pt-1">
            <Skeleton className="h-6 w-36 rounded-full" />
            <Skeleton className="h-3 w-44 rounded-full" />
          </div>
          <Hairline />
          <Skeleton className="h-10 w-full rounded-full" />
          <div className="space-y-1">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3 px-3 py-3">
                <Skeleton className="h-9 w-9 shrink-0 rounded-[0.8rem]" />
                <div className="min-w-0 flex-1 space-y-2">
                  <Skeleton className="h-3 w-4/5 rounded-full" />
                  <Skeleton className="h-2.5 w-1/2 rounded-full" />
                </div>
              </div>
            ))}
          </div>
        </Bezel>

        {/* Composer */}
        <Bezel size="lg" lifted className="min-w-0 lg:col-span-8 xl:col-span-6" coreClassName="flex flex-col">
          <div className="flex items-start gap-3.5 px-5 pb-5 pt-6 md:px-7 md:pt-7">
            <Skeleton className="h-11 w-11 shrink-0 rounded-[0.95rem]" />
            <div className="min-w-0 flex-1 space-y-2.5">
              <Skeleton className="h-6 w-3/4 rounded-xl" />
              <Skeleton className="h-3 w-1/3 rounded-full" />
            </div>
          </div>
          <Hairline />
          <div className="grid gap-4 px-5 py-5 sm:grid-cols-2 md:px-7">
            <Skeleton className="h-[3.25rem] w-full rounded-2xl" />
            <Skeleton className="h-[3.25rem] w-full rounded-2xl" />
          </div>
          <div className="px-5 md:px-7">
            <Skeleton className="h-[18rem] w-full rounded-2xl md:h-[22rem]" />
          </div>
          <div className="mt-5 space-y-4 px-5 pb-6 md:px-7 md:pb-7">
            <Skeleton className="h-14 w-full rounded-2xl" />
            <div className="flex justify-end gap-3">
              <Skeleton className="h-11 w-32 rounded-full" />
              <Skeleton className="h-11 w-28 rounded-full" />
            </div>
          </div>
        </Bezel>

        {/* Assistant rail */}
        <div className="grid min-w-0 grid-cols-1 content-start gap-6 md:grid-cols-2 lg:col-span-12 xl:col-span-3 xl:grid-cols-1">
          <Bezel size="md" coreClassName="space-y-4 p-4">
            <div className="flex items-center gap-2.5">
              <Skeleton className="h-8 w-8 rounded-full" />
              <Skeleton className="h-4 w-28 rounded-full" />
            </div>
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-[6.5rem] w-full rounded-2xl" />
            ))}
          </Bezel>
          <Bezel size="md" coreClassName="space-y-5 p-4">
            <div className="flex items-center gap-2.5">
              <Skeleton className="h-8 w-8 rounded-full" />
              <Skeleton className="h-4 w-32 rounded-full" />
            </div>
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3 px-1">
                <Skeleton className="h-7 w-7 shrink-0 rounded-full" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-2.5 w-12 rounded-full" />
                  <Skeleton className="h-3 w-28 rounded-full" />
                </div>
              </div>
            ))}
          </Bezel>
        </div>
      </div>
      <span className="sr-only">Loading…</span>
    </div>
  );
}
