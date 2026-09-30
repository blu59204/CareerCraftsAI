import { InterviewLoadingSkeleton } from "@/components/interview/InterviewSkeleton";

// Shown only while the server redirect to /interview?tab=prep resolves.
export default function InterviewPrepLoading() {
  return <InterviewLoadingSkeleton />;
}
