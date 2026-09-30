import { Bezel } from "@/components/vanguard/Bezel";
import { Skeleton } from "@/components/vanguard/Display";
import { Screen } from "@/components/vanguard/Screen";

export default function ApplicationsLoading() {
  return (
    <Screen>
      <div aria-busy="true" aria-label="Loading application tracker" className="space-y-6 md:space-y-8">
        <header className="space-y-4 pt-2 md:pt-4">
          <div className="min-w-0 space-y-4">
            <Skeleton className="h-6 w-32 rounded-full" />
            <div className="space-y-3">
              <Skeleton className="h-12 w-[min(34rem,90%)] rounded-2xl md:h-16" />
            </div>
            <Skeleton className="h-5 w-[min(36rem,95%)] rounded-full" />
            <div className="flex flex-wrap gap-3 pt-2">
              <Skeleton className="h-11 w-36 rounded-full" />
            </div>
          </div>
        </header>
        <Bezel coreClassName="grid grid-cols-2 gap-px overflow-hidden bg-foreground/[0.06] dark:bg-white/[0.06] sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="min-w-0 space-y-3 bg-card px-4 py-4 md:px-5 md:py-5">
              <Skeleton className="h-3 w-16 rounded-full" />
              <Skeleton className="h-10 w-14 rounded-xl" />
            </div>
          ))}
        </Bezel>

        <section className="space-y-5">
          <Bezel size="md" coreClassName="flex flex-wrap items-center gap-3 p-3">
            <Skeleton className="h-12 w-full rounded-2xl sm:flex-1" />
            <Skeleton className="h-9 w-40 rounded-full" />
            <Skeleton className="h-9 w-24 rounded-full" />
          </Bezel>
          <Skeleton className="h-4 w-48 rounded-full" />
          <Bezel size="md" coreClassName="space-y-3 p-4">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-16 w-full rounded-xl" />)}
          </Bezel>
        </section>
      </div>
    </Screen>
  );
}
