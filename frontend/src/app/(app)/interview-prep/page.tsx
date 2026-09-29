import { redirect } from "next/navigation";

// Interview Prep now lives on the merged Interview screen (Prep plan tab).
export default function InterviewPrepPage() {
  redirect("/interview?tab=prep");
}
