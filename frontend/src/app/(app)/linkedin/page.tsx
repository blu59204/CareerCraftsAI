"use client";

import Link from "next/link";
import { ProfilePdfUpload } from "@/components/linkedin/ProfilePdfUpload";
import { Screen, Eyebrow } from "@/components/vanguard";

export default function LinkedInPage() {
  return (
    <Screen>
      <header className="mb-8 space-y-5 pt-2 md:pt-4">
        <Eyebrow>LinkedIn profile</Eyebrow>
        <h1 className="text-balance text-[clamp(2rem,3.5vw,3.5rem)] font-semibold leading-[1.05] tracking-[-0.045em]">LinkedIn presence tuned to one role.</h1>
        <p className="max-w-2xl text-muted-foreground">Upload your exported profile and review suggested edits grounded in your experience.</p>
        <Link className="inline-block text-sm underline underline-offset-4" href="/linkedin/outreach">Recruiter outreach</Link>
      </header>
      <ProfilePdfUpload />
    </Screen>
  );
}
