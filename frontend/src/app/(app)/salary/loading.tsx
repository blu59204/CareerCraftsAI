import { Bezel } from '@/components/vanguard/Bezel'
import { Skeleton } from '@/components/vanguard/Display'

/** Mirrors the Salary Editorial Split: headline + form on the left, report on the right. */
export default function SalaryLoading() {
  return (
    <div className="relative mx-auto w-full min-w-0 max-w-[1400px] pb-8 font-geist md:pb-12" aria-busy="true" aria-label="Loading salary intelligence">
      <div className="grid grid-cols-1 gap-6 pt-2 md:pt-4 lg:grid-cols-12 lg:gap-8">
        {/* Left: eyebrow, headline, description, form */}
        <div className="min-w-0 lg:col-span-5">
          <Skeleton className="h-6 w-28 rounded-full" />
          <div className="mt-5 space-y-3">
            <Skeleton className="h-12 w-40 rounded-2xl sm:h-14" />
            <Skeleton className="h-12 w-64 rounded-2xl sm:h-14" />
          </div>
          <div className="mt-5 space-y-2">
            <Skeleton className="h-4 w-full max-w-[46ch] rounded-full" />
            <Skeleton className="h-4 w-3/4 rounded-full" />
          </div>
          <Bezel className="mt-8" coreClassName="space-y-5 p-5 md:p-6">
            <div className="space-y-2">
              <Skeleton className="h-3 w-20 rounded-full" />
              <Skeleton className="h-[3.25rem] w-full rounded-2xl" />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="space-y-2">
                  <Skeleton className="h-3 w-16 rounded-full" />
                  <Skeleton className="h-[3.25rem] w-full rounded-2xl" />
                </div>
              ))}
            </div>
            <Skeleton className="h-14 w-full rounded-full" />
          </Bezel>
        </div>

        {/* Right: report heading + percentile band + comp/offer + script */}
        <div className="min-w-0 space-y-6 lg:col-span-7 lg:pt-2">
          <div className="flex items-end justify-between gap-4">
            <div className="space-y-4">
              <Skeleton className="h-6 w-20 rounded-full" />
              <Skeleton className="h-8 w-60 rounded-2xl" />
            </div>
            <Skeleton className="h-7 w-32 rounded-full" />
          </div>
          <Bezel coreClassName="space-y-8 p-6 md:p-8">
            <div className="space-y-3">
              <Skeleton className="h-3 w-40 rounded-full" />
              <Skeleton className="h-14 w-56 rounded-2xl" />
            </div>
            <Skeleton className="h-10 w-full rounded-full" />
            <div className="space-y-5">
              {[0.45, 0.62, 0.8, 0.94].map((w) => (
                <div key={w} className="grid grid-cols-[4.5rem_minmax(0,1fr)] items-center gap-4">
                  <Skeleton className="h-3 w-10 rounded-full" />
                  <Skeleton className="h-2.5 rounded-full" />
                </div>
              ))}
            </div>
          </Bezel>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Bezel size="md" coreClassName="space-y-4 p-6">
              <Skeleton className="h-8 w-40 rounded-full" />
              <Skeleton className="h-7 w-48 rounded-2xl" />
            </Bezel>
            <Bezel size="md" coreClassName="space-y-4 p-6">
              <Skeleton className="h-8 w-32 rounded-full" />
              <Skeleton className="h-7 w-36 rounded-2xl" />
            </Bezel>
          </div>
          <Bezel coreClassName="space-y-4 p-6 md:p-8">
            <Skeleton className="h-8 w-48 rounded-full" />
            <Skeleton className="h-4 w-full rounded-full" />
            <Skeleton className="h-4 w-11/12 rounded-full" />
            <Skeleton className="h-4 w-4/5 rounded-full" />
            <Skeleton className="h-16 w-full rounded-2xl" />
          </Bezel>
        </div>
      </div>
    </div>
  )
}
