import { redirect } from "next/navigation";

// Fallback only: next.config.js redirects /interview-prep → /interview?tab=prep
// before this route renders. Kept so client-side navigations still land on
// the merged Interview screen (Prep plan tab).
export default function InterviewPrepPage() {
  redirect("/interview?tab=prep");
}
