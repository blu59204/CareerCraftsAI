import { Bezel } from "@/components/vanguard/Bezel";
import { Skeleton } from "@/components/vanguard/Display";
import { Screen } from "@/components/vanguard/Screen";

const COLUMNS = 6;

export default function ApplicationsLoading() {
  return (
    <Screen>
      <div aria-busy="true" aria-label="Loading application tracker" className="space-y-20 md:space-y-28">
        <header className="grid gap-10 pb-4 pt-6 md:pb-6 md:pt-14 lg:grid-cols-12 lg:items-end">
          <div className="min-w-0 space-y-6 lg:col-span-7 xl:col-span-8">
            <Skeleton className="h-6 w-32 rounded-full" />
            <div className="space-y-3">
              <Skeleton className="h-12 w-[min(34rem,90%)] rounded-2xl md:h-16" />
              <Skeleton className="h-12 w-[min(22rem,70%)] rounded-2xl md:h-16" />
            </div>
            <Skeleton className="h-5 w-[min(36rem,95%)] rounded-full" />
            <div className="flex flex-wrap gap-3 pt-2">
              <Skeleton className="h-[3.25rem] w-full rounded-2xl sm:w-[22rem]" />
              <Skeleton className="h-11 w-36 rounded-full" />
            </div>
          </div>
          <div className="min-w-0 lg:col-span-5 xl:col-span-4">
            <Bezel coreClassName="grid grid-cols-2 gap-px overflow-hidden bg-foreground/[0.06] dark:bg-white/[0.06] md:grid-cols-4 lg:grid-cols-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="space-y-4 bg-card px-5 py-6 md:px-7 md:py-8 lg:px-6 lg:py-6">
                  <Skeleton className="h-3 w-16 rounded-full" />
                  <Skeleton className="h-10 w-14 rounded-xl" />
                </div>
              ))}
            </Bezel>
          </div>
        </header>

        <section className="space-y-5">
          <div className="flex items-center justify-between gap-3">
            <Skeleton className="h-4 w-48 rounded-full" />
            <Skeleton className="h-9 w-28 rounded-full" />
          </div>
          <div className="flex gap-4 overflow-hidden p-1">
            {Array.from({ length: COLUMNS }).map((_, i) => (
              <Bezel key={i} size="md" tone="muted" className="w-[17.25rem] shrink-0 md:w-[18.5rem]" coreClassName="min-h-[24rem] space-y-2.5 p-2.5">
                <Skeleton className="mx-2 mb-3 mt-2 h-4 w-24 rounded-full" />
                {Array.from({ length: 3 - (i % 2) }).map((__, j) => (
                  <Skeleton key={j} className="h-28 rounded-[1.15rem]" />
                ))}
              </Bezel>
            ))}
          </div>
        </section>
      </div>
    </Screen>
  );
}
