import { Bezel } from "@/components/vanguard/Bezel";
import { Hairline, Skeleton } from "@/components/vanguard/Display";

const PARAGRAPHS = [
  ["w-2/5"],
  ["w-full", "w-11/12", "w-full", "w-3/5"],
  ["w-full", "w-10/12", "w-full", "w-11/12", "w-2/5"],
  ["w-full", "w-9/12", "w-1/2"],
] as const;

/** Mirrors the Editorial Split of the cover letter screen: brief on the left, paper on the right. */
export default function CoverLetterLoading() {
  return (
    <div
      role="status"
      aria-label="Loading cover letter writer"
      className="relative mx-auto w-full max-w-[1400px] pb-24 font-geist md:pb-40"
    >
      <div className="grid grid-cols-1 gap-10 pt-6 md:pt-10 lg:grid-cols-12 lg:gap-12 xl:gap-16">
        {/* Left: headline + brief */}
        <div className="min-w-0 space-y-10 lg:col-span-5">
          <div>
            <Skeleton className="h-6 w-24 rounded-full" />
            <Skeleton className="mt-6 h-12 w-4/5 rounded-2xl sm:h-14" />
            <Skeleton className="mt-3 h-12 w-3/5 rounded-2xl sm:h-14" />
            <Skeleton className="mt-6 h-4 w-11/12 rounded-full" />
            <Skeleton className="mt-2.5 h-4 w-2/3 rounded-full" />
          </div>
          <div className="space-y-7">
            <div className="space-y-2">
              <Skeleton className="h-3.5 w-36 rounded-full" />
              <Skeleton className="h-[10.5rem] w-full rounded-2xl md:h-[11.5rem]" />
            </div>
            <div className="space-y-3">
              <Skeleton className="h-3.5 w-12 rounded-full" />
              <Skeleton className="h-10 w-full max-w-md rounded-full" />
            </div>
            <Skeleton className="h-11 w-56 rounded-full" />
          </div>
        </div>

        {/* Right: the paper */}
        <div className="min-w-0 space-y-4 lg:col-span-7">
          <div className="flex items-center justify-between gap-3">
            <Skeleton className="h-6 w-40 rounded-full" />
            <Skeleton className="h-9 w-44 rounded-full" />
          </div>
          <Bezel size="lg" coreClassName="flex flex-col overflow-hidden">
            <div className="flex items-center justify-between gap-3 px-6 py-4 md:px-10">
              <Skeleton className="h-3.5 w-32 rounded-full" />
              <Skeleton className="h-3.5 w-24 rounded-full" />
            </div>
            <Hairline />
            <div className="min-h-[26rem] space-y-7 px-6 py-10 md:min-h-[30rem] md:px-12 md:py-12">
              {PARAGRAPHS.map((para, p) => (
                <div key={p} className="space-y-3">
                  {para.map((w, i) => (
                    <Skeleton key={i} className={`h-3 rounded-full ${w}`} />
                  ))}
                </div>
              ))}
            </div>
            <Hairline />
            <div className="flex items-center justify-between gap-3 px-6 py-3.5 md:px-10">
              <Skeleton className="h-3 w-28 rounded-full" />
              <Skeleton className="h-3 w-40 rounded-full" />
            </div>
          </Bezel>
        </div>
      </div>
      <span className="sr-only">Loading…</span>
    </div>
  );
}
