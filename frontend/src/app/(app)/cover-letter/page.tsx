"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { FileText, Wand2, CloudUpload, ChevronDown, Loader2, Copy, Download } from "lucide-react";
import { toast } from "sonner";
import { fadeUp } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { CommandHeader } from "@/components/immersive/CommandHeader";
import { apiClient } from "@/lib/api";

const TONES = ["Professional", "Enthusiastic", "Concise", "Story-driven"] as const;
type Tone = (typeof TONES)[number];

export default function CoverLetterPage() {
  const [jd, setJd] = useState("");
  const [tone, setTone] = useState<Tone>("Professional");
  const [letter, setLetter] = useState("");
  const [generating, setGenerating] = useState(false);

  const generate = async () => {
    setGenerating(true);
    const toneMap: Record<Tone, "formal" | "casual" | "bold"> = {
      Professional: "formal",
      Concise: "formal",
      Enthusiastic: "casual",
      "Story-driven": "bold",
    };
    try {
      const { data } = await apiClient.post<{
        run_id: string; status: string; content: string | null; tone: string | null;
      }>("/cover-letter/generate", {
        tone: toneMap[tone],
        jd_text: jd || undefined,
      });
      if (data.content) {
        setLetter(data.content);
        toast.success("Cover letter generated");
      } else {
        toast.error("No cover letter returned — check your AI model settings");
      }
    } catch {
      toast.error("Generation failed — check your AI model settings");
    } finally {
      setGenerating(false);
    }
  };

  const copyToClipboard = () => {
    if (letter) {
      navigator.clipboard.writeText(letter);
      toast.success("Copied to clipboard");
    }
  };

  const downloadTxt = () => {
    if (!letter) return;
    const blob = new Blob([letter], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "cover-letter.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <motion.div className="space-y-6 p-6" variants={fadeUp} initial="hidden" animate="visible">
      <CommandHeader
        eyebrow="AI Writer"
        title="Cover Letter"
        description="AI‑generated, tone‑aware cover letters tailored to each job description."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Input */}
        <div className="rounded-3xl border border-border bg-card/60 p-6 space-y-4">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" />
            <span className="font-medium text-sm">Job Description</span>
            <span className="text-xs text-muted-foreground">(optional but recommended)</span>
          </div>
          <textarea
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            placeholder="Paste the job description here to get a tailored cover letter…"
            className="h-32 w-full resize-none rounded-2xl border border-border bg-background/60 px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          <div>
            <div className="mb-2 text-xs font-medium text-foreground">Tone</div>
            <div className="flex flex-wrap gap-2">
              {TONES.map((t) => (
                <button
                  key={t}
                  onClick={() => setTone(t)}
                  className={`rounded-full px-3 py-1 text-xs transition-colors ${
                    tone === t
                      ? "bg-primary/10 text-primary font-medium"
                      : "border border-border text-muted-foreground hover:bg-card"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
          <LiquidGlassButton tone="primary" size="sm" disabled={generating} onClick={generate}>
            {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
            {generating ? "Generating…" : "Generate Cover Letter"}
          </LiquidGlassButton>
        </div>

        {/* Output */}
        <div className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">Cover Letter</span>
            {letter && (
              <div className="flex gap-2">
                <button
                  onClick={copyToClipboard}
                  className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:bg-card transition-colors"
                >
                  <Copy className="h-3 w-3 inline mr-1" />Copy
                </button>
                <button
                  onClick={downloadTxt}
                  className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:bg-card transition-colors"
                >
                  <Download className="h-3 w-3 inline mr-1" />Download
                </button>
              </div>
            )}
          </div>
          {generating ? (
            <div className="space-y-2">
              {[100, 80, 90, 60, 70, 85, 75, 55, 65].map((w, i) => (
                <div key={i} className="shimmer h-4 rounded-full" style={{ width: `${w}%` }} />
              ))}
            </div>
          ) : letter ? (
            <textarea
              value={letter}
              onChange={(e) => setLetter(e.target.value)}
              className="h-72 w-full resize-none rounded-2xl border border-border bg-background/60 px-4 py-3 text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          ) : (
            <div className="flex h-48 items-center justify-center rounded-2xl border border-dashed border-border text-sm text-muted-foreground">
              Your cover letter will appear here
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
