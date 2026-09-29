import { Bezel } from '@/components/vanguard/Bezel'
import { Skeleton } from '@/components/vanguard/Display'
import { Screen } from '@/components/vanguard/Screen'

/**
 * Route-level loading state for /company. Mirrors the page: hero with the
 * search island and agent-run aside, then the asymmetrical bento briefing.
 */
export default function CompanyLoading() {
  return (
    <Screen>
      <header aria-busy="true" className="grid gap-10 pb-12 pt-6 md:pb-20 md:pt-14 lg:grid-cols-12 lg:items-end">
        <p role="status" className="sr-only">Loading company research</p>
        <div className="min-w-0 lg:col-span-7 xl:col-span-8">
          <Skeleton className="h-6 w-28 rounded-full" />
          <Skeleton className="mt-6 h-14 w-full max-w-[34rem] md:h-16" />
          <Skeleton className="mt-3 h-14 w-4/5 max-w-[28rem] md:h-16" />
          <Skeleton className="mt-6 h-4 w-full max-w-[36rem]" />
          <Skeleton className="mt-2 h-4 w-3/4 max-w-[28rem]" />
          <Bezel size="lg" className="mt-8 w-full max-w-2xl" coreClassName="flex flex-col gap-2 p-2 sm:flex-row sm:items-center">
            <Skeleton className="h-14 flex-1" />
            <Skeleton className="h-14 w-full rounded-full sm:w-40" />
          </Bezel>
        </div>
        <div className="min-w-0 lg:col-span-5 xl:col-span-4">
          <Bezel size="lg" coreClassName="space-y-5 p-6 md:p-7">
            <div className="flex items-center justify-between">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-3 w-28" />
            </div>
            <Skeleton className="h-6 w-28 rounded-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-4/5" />
            <div className="grid grid-cols-2 gap-4 pt-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          </Bezel>
        </div>
      </header>

      <section className="space-y-8 md:space-y-10">
        <div className="space-y-4">
          <Skeleton className="h-6 w-24 rounded-full" />
          <Skeleton className="h-9 w-72 max-w-full" />
          <Skeleton className="h-4 w-56 max-w-full" />
        </div>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-12">
          <Bezel tone="primary" className="md:col-span-12 lg:col-span-8" coreClassName="space-y-4 p-7 md:p-10">
            <Skeleton className="h-8 w-40" />
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-5 w-11/12" />
            <Skeleton className="h-5 w-4/5" />
            <Skeleton className="h-5 w-2/3" />
          </Bezel>
          <Bezel className="md:col-span-12 lg:col-span-4" coreClassName="space-y-5 p-7">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </Bezel>
          <Bezel className="md:col-span-7" coreClassName="space-y-4 p-7 md:p-8">
            <Skeleton className="h-8 w-32" />
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-3/4" />
          </Bezel>
          <Bezel className="md:col-span-5" coreClassName="space-y-4 p-7 md:p-8">
            <Skeleton className="h-8 w-44" />
            <Skeleton className="h-14 w-32" />
            <Skeleton className="h-3 w-full rounded-full" />
          </Bezel>
          <Bezel className="md:col-span-5 lg:col-span-4" coreClassName="space-y-4 p-7">
            <Skeleton className="h-8 w-28" />
            <div className="flex flex-wrap gap-2">
              <Skeleton className="h-7 w-16 rounded-full" />
              <Skeleton className="h-7 w-20 rounded-full" />
              <Skeleton className="h-7 w-14 rounded-full" />
              <Skeleton className="h-7 w-24 rounded-full" />
            </div>
          </Bezel>
          <Bezel className="md:col-span-7 lg:col-span-8" coreClassName="space-y-5 p-7 md:p-8">
            <Skeleton className="h-8 w-36" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </Bezel>
        </div>
      </section>
    </Screen>
  )
}
