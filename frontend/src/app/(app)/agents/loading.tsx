import { Bezel } from "@/components/vanguard/Bezel";
import { Skeleton } from "@/components/vanguard/Display";

// Mirrors the agents cockpit: compact hero + stat aside, four-group agent
// bento (5/7 · 7/5 spans), then the span-8 run console and span-4 rail.
const GROUPS = [
  { span: "lg:col-span-5", tiles: 3, wideFirst: true, cols: "sm:grid-cols-2" },
  { span: "lg:col-span-7", tiles: 4, wideFirst: false, cols: "sm:grid-cols-2" },
  { span: "lg:col-span-7", tiles: 4, wideFirst: false, cols: "sm:grid-cols-2" },
  { span: "lg:col-span-5", tiles: 2, wideFirst: false, cols: "grid-cols-1" },
] as const;

export default function AgentsLoading() {
  return (
    <div
      className="relative mx-auto w-full min-w-0 max-w-[1400px] space-y-6 pb-8 font-geist md:space-y-8 md:pb-12"
      role="status"
      aria-label="Loading agents"
    >
      <div className="grid gap-6 pb-2 pt-2 md:pb-4 md:pt-4 lg:grid-cols-12 lg:items-end">
        <div className="space-y-6 lg:col-span-7 xl:col-span-8">
          <Skeleton className="h-6 w-32 rounded-full" />
          <Skeleton className="h-14 w-full max-w-md md:h-20" />
          <Skeleton className="h-5 w-full max-w-lg" />
          <Skeleton className="h-9 w-56 rounded-full" />
        </div>
        <div className="lg:col-span-5 xl:col-span-4">
          <Bezel size="md" coreClassName="grid grid-cols-3 gap-4 p-5">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="space-y-3">
                <Skeleton className="h-3 w-16 rounded-full" />
                <Skeleton className="h-8 w-10" />
              </div>
            ))}
          </Bezel>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-12">
        {GROUPS.map((group, gi) => (
          <Bezel key={gi} className={group.span} coreClassName="p-3 md:p-4">
            <div className="flex items-center justify-between px-2 pb-3 pt-1">
              <Skeleton className="h-4 w-40 rounded-full" />
              <Skeleton className="h-3 w-6 rounded-full" />
            </div>
            <div className={`grid grid-cols-1 gap-1.5 ${group.cols}`}>
              {Array.from({ length: group.tiles }).map((_, ti) => (
                <Skeleton
                  key={ti}
                  className={`h-[68px] rounded-[1.1rem] ${group.wideFirst && ti === 0 ? "sm:col-span-2" : ""}`}
                />
              ))}
            </div>
          </Bezel>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <Bezel className="lg:col-span-8" coreClassName="space-y-7 p-5 md:p-7">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <Skeleton className="h-12 w-12 rounded-full" />
              <div className="space-y-3">
                <Skeleton className="h-5 w-20 rounded-full" />
                <Skeleton className="h-8 w-56" />
                <Skeleton className="h-4 w-40" />
              </div>
            </div>
            <Skeleton className="h-11 w-36 rounded-full" />
          </div>
          <Skeleton className="h-36 w-full rounded-2xl" />
          <Skeleton className="h-[268px] w-full rounded-[1.5rem]" />
        </Bezel>

        <div className="space-y-6 lg:col-span-4">
          <Bezel coreClassName="space-y-4 p-5">
            <Skeleton className="h-8 w-32 rounded-full" />
            <Skeleton className="h-12 w-full rounded-2xl" />
            <Skeleton className="h-12 w-full rounded-2xl" />
            <Skeleton className="h-14 w-full rounded-2xl" />
          </Bezel>
          <Bezel coreClassName="space-y-2 p-5">
            <Skeleton className="mb-3 h-8 w-40 rounded-full" />
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-[76px] w-full rounded-2xl" />
            ))}
          </Bezel>
        </div>
      </div>
    </div>
  );
}
