"use client";
import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { IslandButton } from "@/components/vanguard";
import { Paperclip } from "@phosphor-icons/react";
import { uploadResume } from "@/lib/resume-upload";
import { getApiErrorMessage } from "@/lib/api";

export function ResumeUpload() {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(false);
  const cache = useQueryClient();
  return <div className="px-5 py-3">
    <input ref={input} className="sr-only" type="file" accept=".pdf,.docx,.txt" aria-label="Upload resume file" onChange={async e => {
      const file = e.target.files?.[0]; if (!file) return;
      setBusy(true); setError(false); setMessage("Uploading resume...");
      try {
        const doc = await uploadResume(file);
        setMessage(`${doc.filename} saved as your active resume.${doc.warning ? ` ${doc.warning}` : " Ready for job matching and applications."}`);
        await Promise.all(["resume-docs", "job-search-profile", "computer-resumes"].map(key => cache.invalidateQueries({ queryKey: [key] })));
      } catch (err) { setError(true); setMessage(getApiErrorMessage(err, "Resume upload failed. Try again.")); }
      finally { setBusy(false); if (input.current) input.current.value = ""; }
    }} />
    <IslandButton size="sm" tone="quiet" disabled={busy} icon={<Paperclip size={16} />} onClick={() => input.current?.click()}>{busy ? "Uploading..." : "Upload resume"}</IslandButton>
    <p role={error ? "alert" : "status"} className={`mt-2 text-xs ${error ? "text-destructive" : "text-muted-foreground"}`}>{message || "PDF, DOCX or TXT, up to 10 MB. Saved to your account; no AI model needed."}</p>
  </div>;
}
