import { Bezel } from "@/components/vanguard/Bezel";
import { Skeleton } from "@/components/vanguard/Display";
import { Screen } from "@/components/vanguard/Screen";

/** Mirrors the Editorial Split: type + primary resume on the left, working area on the right. */
export default function ResumeLoading() {
  return (
    <Screen>
      <div role="status" aria-label="Loading resume workspace" className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:gap-x-8">
        <div className="min-w-0 space-y-6 pt-2 md:pt-4 lg:col-span-5 xl:col-span-4">
          <Skeleton className="h-6 w-36 rounded-full" />
          <div className="space-y-3">
            <Skeleton className="h-14 w-4/5 rounded-2xl" />
            <Skeleton className="h-14 w-full rounded-2xl" />
          </div>
          <div className="space-y-2">
            <Skeleton className="h-4 w-full rounded-full" />
            <Skeleton className="h-4 w-2/3 rounded-full" />
          </div>
          <div className="flex gap-2">
            <Skeleton className="h-9 w-24 rounded-full" />
            <Skeleton className="h-9 w-32 rounded-full" />
            <Skeleton className="h-9 w-24 rounded-full" />
          </div>
          <Bezel coreClassName="flex items-center gap-5 p-6">
            <Skeleton className="h-32 w-32 shrink-0 rounded-full" />
            <div className="flex-1 space-y-3">
              <Skeleton className="h-4 w-24 rounded-full" />
              <Skeleton className="h-4 w-full rounded-full" />
              <Skeleton className="h-3 w-2/3 rounded-full" />
            </div>
          </Bezel>
          <Bezel tone="muted" coreClassName="p-6">
            <Skeleton className="h-24 w-full" />
          </Bezel>
        </div>

        <div className="min-w-0 space-y-6 lg:col-span-7 lg:pt-10 xl:col-span-8">
          <Skeleton className="h-11 w-full max-w-md rounded-full" />
          <Bezel coreClassName="space-y-4 p-6">
            <Skeleton className="h-8 w-56 rounded-full" />
            <Skeleton className="h-36 w-full" />
            <div className="flex justify-end gap-2">
              <Skeleton className="h-9 w-32 rounded-full" />
              <Skeleton className="h-9 w-36 rounded-full" />
            </div>
          </Bezel>
          <Bezel coreClassName="space-y-4 p-6">
            <Skeleton className="h-6 w-40 rounded-full" />
            <Skeleton className="h-[28rem] w-full" />
          </Bezel>
        </div>
      </div>
    </Screen>
  );
}
