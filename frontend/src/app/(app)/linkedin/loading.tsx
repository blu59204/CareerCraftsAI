import { Bezel } from "@/components/vanguard/Bezel";
import { Skeleton } from "@/components/vanguard/Display";
import { Screen } from "@/components/vanguard/Screen";

/**
 * Mirrors the LinkedIn editorial split: statement + target-role controls on
 * the left, the run-status rail and stacked before/after section cards on the
 * right. Server component — no client-only imports.
 */
export default function LinkedInLoading() {
  return (
    <Screen>
      <div
        role="status"
        aria-label="Loading LinkedIn"
        className="grid grid-cols-1 gap-12 pt-6 md:pt-14 lg:grid-cols-12 lg:gap-14"
      >
        <div className="space-y-8 lg:col-span-5">
          <div>
            <Skeleton className="h-6 w-32 rounded-full" />
            <Skeleton className="mt-6 h-12 w-4/5 rounded-2xl md:h-16" />
            <Skeleton className="mt-3 h-12 w-3/5 rounded-2xl md:h-16" />
            <Skeleton className="mt-6 h-4 w-full max-w-[46ch] rounded-full" />
            <Skeleton className="mt-2.5 h-4 w-4/5 max-w-[40ch] rounded-full" />
          </div>
          <div className="space-y-3">
            <Skeleton className="h-3 w-20 rounded-full" />
            <Bezel size="md" coreClassName="p-0">
              <Skeleton className="h-11 w-full rounded-[calc(1rem-0.25rem)]" />
            </Bezel>
            <div className="flex gap-2.5 pt-1">
              <Skeleton className="h-11 w-44 rounded-full" />
              <Skeleton className="h-11 w-32 rounded-full" />
            </div>
          </div>
        </div>

        <div className="space-y-6 lg:col-span-7">
          <Bezel size="md" coreClassName="flex items-center justify-between gap-4 px-5 py-4">
            <Skeleton className="h-6 w-36 rounded-full" />
            <Skeleton className="h-7 w-20 rounded-full" />
          </Bezel>
          <Skeleton className="h-8 w-56 rounded-full" />
          {[0, 1, 2].map((i) => (
            <Bezel key={i} size="lg" coreClassName="space-y-4 p-6 md:p-7">
              <div className="flex items-center justify-between">
                <Skeleton className="h-5 w-40 rounded-full" />
                <Skeleton className="h-6 w-20 rounded-full" />
              </div>
              <Skeleton className="h-1 w-full rounded-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className={i === 1 ? "h-36 w-full" : "h-24 w-full"} />
            </Bezel>
          ))}
        </div>
      </div>
    </Screen>
  );
}
