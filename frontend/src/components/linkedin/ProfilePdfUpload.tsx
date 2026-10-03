"use client";

import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { X } from "@phosphor-icons/react";
import { apiClient, getApiErrorMessage } from "@/lib/api";
import { profileResultSchema } from "@/lib/profile-contracts";
import { Bezel, Input, IslandButton } from "@/components/vanguard";
import { cn } from "@/lib/utils";

export function ProfilePdfUpload() {
  const [targetRole, setTargetRole] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const generation = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const analysis = useMutation({
    mutationFn: async () => {
      const requestGeneration = generation.current;
      if (!file || !targetRole.trim()) throw new Error("Select a PDF and enter a target role.");
      if (!file.name.toLowerCase().endsWith(".pdf") || file.size > 5 * 1024 * 1024) throw new Error("Choose a PDF no larger than 5 MB.");
      const body = new FormData();
      body.append("file", file);
      body.append("target_role", targetRole.trim());
      const response = await apiClient.post("/linkedin/profile/optimize", body, {
        headers: { "Content-Type": "multipart/form-data" }, timeout: 130_000,
      });
      if (generation.current !== requestGeneration) throw new Error("The selected profile changed. Run analysis again.");
      return profileResultSchema.parse(response.data);
    },
    onError: (err) => setError(getApiErrorMessage(err, "Could not analyze this PDF. Check your model settings and try again.")),
  });

  const reset = () => { generation.current += 1; analysis.reset(); setError(""); };

  const handleFileSelect = (f: File | null) => {
    reset();
    setFile(f);
  };

  const handleDragOver = (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (analysis.isPending) return;
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      handleFileSelect(droppedFile);
    }
  };

  const handleRemove = () => {
    reset();
    setFile(null);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  return (
    <div className="space-y-6">
      <Bezel coreClassName="space-y-4 p-5 md:p-6">
        <p id="linkedin-pdf-help" className="text-sm text-muted-foreground">Profile → More → Save to PDF → upload. Use the text PDF exported by LinkedIn, up to 5 MB. Suggestions are for you to review and apply.</p>
        <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); setError(""); analysis.mutate(); }}>
          <div className="space-y-2">
            <label htmlFor="linkedin-profile-pdf" className="block text-sm">LinkedIn profile PDF</label>
            <label
              htmlFor="linkedin-profile-pdf"
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={cn(
                "block rounded-lg border-2 border-dashed px-4 py-6 text-center transition-colors cursor-pointer",
                "focus-within:ring-2 focus-within:ring-ring",
                dragActive ? "border-primary bg-primary/5" : "border-border hover:border-muted-foreground/50",
                analysis.isPending && "pointer-events-none opacity-60"
              )}
            >
              <input
                id="linkedin-profile-pdf"
                ref={inputRef}
                type="file"
                accept=".pdf,application/pdf"
                aria-describedby="linkedin-pdf-help"
                disabled={analysis.isPending}
                onChange={(event) => handleFileSelect(event.target.files?.[0] ?? null)}
                className="sr-only"
              />
              {file ? (
                <div className="space-y-2">
                  <p className="text-sm font-medium text-foreground">{file.name}</p>
                  <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
                  <button
                    type="button"
                    onClick={handleRemove}
                    disabled={analysis.isPending}
                    className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
                    aria-label="Remove file"
                  >
                    <X size={14} />
                    Remove
                  </button>
                </div>
              ) : (
                <div className="space-y-1">
                  <p className="text-sm font-medium text-foreground">Drop your PDF here or click to select</p>
                  <p className="text-xs text-muted-foreground">Maximum 5 MB</p>
                </div>
              )}
            </label>
          </div>
          <div>
            <label className="block text-sm mb-2" htmlFor="linkedin-target-role">Target role</label>
            <Input id="linkedin-target-role" value={targetRole} maxLength={200} required disabled={analysis.isPending}
              onChange={(event) => { reset(); setTargetRole(event.target.value); }} placeholder="Senior Python Engineer" />
          </div>
          <IslandButton type="submit" tone="primary" disabled={analysis.isPending || !file || !targetRole.trim()}>{analysis.isPending ? "Analyzing profile…" : "Analyze uploaded profile"}</IslandButton>
          {analysis.isPending && <p role="status">Reading your profile and preparing section edits…</p>}
          {error && <p role="alert" className="text-danger">{error}</p>}
        </form>
      </Bezel>
      {!analysis.data && !analysis.isPending && <p className="text-sm text-muted-foreground">Upload a profile to see concrete before/after edits for headline, about, experience and skills.</p>}
      {analysis.data?.warnings.map((warning) => <p key={warning} role="status" className="text-sm text-muted-foreground">{warning}</p>)}
      {analysis.data?.sections.map((edit) => (
        <Bezel key={edit.section} coreClassName="space-y-4 p-5 md:p-6">
          <h2 className="font-semibold capitalize">{edit.section}</h2>
          <div className="grid gap-5 md:grid-cols-2">
            <div><h3 className="text-sm font-medium">Before</h3><p className="mt-2 whitespace-pre-wrap text-sm">{edit.before || "Not included in the uploaded PDF."}</p></div>
            <div><h3 className="text-sm font-medium">Suggested edit</h3><p className="mt-2 whitespace-pre-wrap text-sm">{edit.after || "Provide the missing details before drafting this section."}</p></div>
          </div>
          <p className="text-sm text-muted-foreground">{edit.reason}</p>
          {edit.gaps.length > 0 && <ul className="list-disc pl-5 text-sm">{edit.gaps.map((gap) => <li key={gap}>{gap}</li>)}</ul>}
          {edit.source_quotes.length > 0 && <details className="text-sm"><summary>Source evidence</summary>{edit.source_quotes.map((quote) => <blockquote className="mt-2 whitespace-pre-wrap" key={quote}>{quote}</blockquote>)}</details>}
        </Bezel>
      ))}
    </div>
  );
}
