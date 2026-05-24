"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Upload, Download, Target, FileText, Wand2, CloudUpload, ChevronDown } from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { AtsScoreRing } from "@/components/resume/AtsScoreRing";
import { KeywordCoverage } from "@/components/resume/KeywordCoverage";
import { SuggestionsList, type Suggestion } from "@/components/resume/SuggestionsList";
import { EmptyState } from "@/components/ui/EmptyState";
import { ResumeTemplates } from "@/components/resume/ResumeTemplates";

// TODO Phase 4 wiring: pull from apiClient.resume.getCurrent() once endpoint is wired.
const MOCK_SUGGESTIONS: Suggestion[] = [
  {
    id: "1",
    original: "Worked on the backend team building REST APIs.",
    suggestion: "Designed and shipped 12 REST endpoints handling 4k+ daily requests; cut p95 latency from 320ms to 110ms.",
  },
  {
    id: "2",
    original: "Built a React dashboard.",
    suggestion: "Built a real-time React dashboard with TanStack Query and WebSockets, used daily by 200+ internal operators.",
  },
];

const COVER_LETTER_TONES = ["Professional", "Enthusiastic", "Concise", "Story-driven"] as const;
type CoverTone = typeof COVER_LETTER_TONES[number];

function CoverLetterGenerator() {
  const [jd, setJd] = useState("");
  const [tone, setTone] = useState<CoverTone>("Professional");
  const [letter, setLetter] = useState("");
  const [generating, setGenerating] = useState(false);
  const [showDriveMenu, setShowDriveMenu] = useState(false);

  const generate = () => {
    setGenerating(true);
    // Simulate generation (TODO: wire to POST /agents/run task_type=cover_letter)
    setTimeout(() => {
      setLetter(`Dear Hiring Manager,

I'm excited to apply for this role. ${jd ? `After reviewing the job description, I'm confident my experience directly aligns with your needs.` : `My background in software engineering makes me a strong candidate.`}

Over the past several years, I have built scalable, production-grade applications — from distributed backend systems to polished React frontends. I thrive in fast-moving environments and have a track record of shipping features that measurably improve user outcomes.

What draws me specifically to your team is the intersection of technical depth and user-focused design. I'd love to bring that same mindset to this role.

I'd be grateful for the opportunity to discuss how my experience could contribute to your team's goals.

Warm regards,
Your Name`);
      setGenerating(false);
    }, 1800);
  };

  const copyToClipboard = () => {
    if (letter) navigator.clipboard.writeText(letter);
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
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Input panel */}
      <div className="space-y-4">
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
              {COVER_LETTER_TONES.map((t) => (
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

          <LiquidGlassButton
            tone="primary"
            size="sm"
            disabled={generating}
            onClick={generate}
          >
            <Wand2 className="h-4 w-4" />
            {generating ? "Generating…" : "Generate Cover Letter"}
          </LiquidGlassButton>
        </div>
      </div>

      {/* Output panel */}
      <div className="rounded-3xl border border-border bg-card/60 p-6">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm font-medium text-foreground">Cover Letter</span>
          {letter && (
            <div className="flex gap-2">
              <button
                onClick={copyToClipboard}
                className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:bg-card transition-colors"
              >
                Copy
              </button>
              <button
                onClick={downloadTxt}
                className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:bg-card transition-colors"
              >
                Download
              </button>
              <div className="relative">
                <button
                  onClick={() => setShowDriveMenu((v) => !v)}
                  className="flex items-center gap-1 rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:bg-card transition-colors"
                >
                  <CloudUpload className="h-3.5 w-3.5" />
                  Drive
                  <ChevronDown className={`h-3 w-3 transition-transform ${showDriveMenu ? "rotate-180" : ""}`} />
                </button>
                <AnimatePresence>
                  {showDriveMenu && (
                    <motion.div
                      initial={{ opacity: 0, y: -8, scale: 0.96 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: -8, scale: 0.96 }}
                      transition={{ duration: 0.15 }}
                      className="absolute right-0 top-9 z-10 min-w-[200px] rounded-2xl border border-border bg-card p-2 shadow-lg"
                    >
                      <button className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-xs hover:bg-muted">
                        <CloudUpload className="h-3.5 w-3.5 text-muted-foreground" />
                        Save to Google Drive
                      </button>
                      <button className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-xs hover:bg-muted">
                        <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                        Save as Google Doc
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          )}
        </div>
        {generating ? (
          <div className="space-y-2">
            {[100, 80, 90, 60, 70, 85].map((w, i) => (
              <div key={i} className={`shimmer h-4 rounded-full`} style={{ width: `${w}%` }} />
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
  );
}

export default function ResumePage() {
  const [suggestions, setSuggestions] = useState<Suggestion[]>(MOCK_SUGGESTIONS);
  const [tab, setTab] = useState<"builder" | "templates" | "history" | "cover-letter">("builder");
  const [activeTemplate, setActiveTemplate] = useState("modern");
  const [jdText, setJdText] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [jdPanelOpen, setJdPanelOpen] = useState(true);
  const [showExportMenu, setShowExportMenu] = useState(false);

  const accept = (id: string) => setSuggestions((s) => s.filter((x) => x.id !== id));
  const reject = (id: string) => setSuggestions((s) => s.filter((x) => x.id !== id));

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <div className="text-sm text-muted-foreground">Resume Workspace</div>
          <h1 className="mt-1 text-3xl font-medium">Tailor your resume.</h1>
        </div>
        <div className="flex gap-2">
          <LiquidGlassButton tone="ghost" size="sm">
            <Upload className="h-4 w-4" /> Upload
          </LiquidGlassButton>
          <div className="relative">
            <LiquidGlassButton
              tone="ghost"
              size="sm"
              onClick={() => setShowExportMenu((v) => !v)}
            >
              <CloudUpload className="h-4 w-4" /> Save to Drive
            </LiquidGlassButton>
            <AnimatePresence>
              {showExportMenu && (
                <motion.div
                  initial={{ opacity: 0, y: -8, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -8, scale: 0.96 }}
                  transition={{ duration: 0.15 }}
                  className="absolute right-0 top-10 z-10 min-w-[200px] rounded-2xl border border-border bg-card p-2 shadow-lg"
                >
                  <button className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm hover:bg-muted">
                    <CloudUpload className="h-4 w-4 text-muted-foreground" /> Save to Google Drive
                  </button>
                  <button className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm hover:bg-muted">
                    <FileText className="h-4 w-4 text-muted-foreground" /> Save as Google Doc
                  </button>
                  <button className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm hover:bg-muted">
                    <Download className="h-4 w-4 text-muted-foreground" /> Download PDF
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          <LiquidGlassButton tone="primary" size="sm">
            <Download className="h-4 w-4" /> Export
          </LiquidGlassButton>
        </div>
      </motion.div>

      <motion.div variants={fadeUp}>
        <div className="flex gap-1 rounded-full border border-border bg-muted/40 p-1 text-sm">
          {(["builder", "templates", "cover-letter", "history"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-full px-4 py-1.5 capitalize transition-colors ${
                tab === t
                  ? "bg-background shadow-sm text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t === "cover-letter" ? "Cover Letter" : t}
            </button>
          ))}
        </div>
      </motion.div>

      {tab === "templates" && (
        <motion.div variants={fadeUp}>
          <ResumeTemplates selected={activeTemplate} onSelect={setActiveTemplate} />
        </motion.div>
      )}

      {tab === "cover-letter" && (
        <motion.div variants={fadeUp}>
          <CoverLetterGenerator />
        </motion.div>
      )}

      {tab === "history" && (
        <motion.div variants={fadeUp}>
          <EmptyState
            title="Resume history"
            description="Previous versions of your resume will appear here."
          />
        </motion.div>
      )}

      {tab === "builder" && (
        <>
        <motion.div variants={fadeUp} className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Target className="h-5 w-5 text-primary" />
              <div className="font-medium">Target Job Description</div>
              {jdText && <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">Active</span>}
            </div>
            <LiquidGlassButton tone="ghost" size="sm" onClick={() => setJdPanelOpen(!jdPanelOpen)}>
              {jdPanelOpen ? "Hide" : "Show JD"}
            </LiquidGlassButton>
          </div>

          {jdPanelOpen && (
            <div className="mt-4 space-y-3">
              <textarea
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
                placeholder="Paste the job description here… CareerCraft AI will analyze requirements, match keywords, and suggest targeted resume bullets."
                className="h-32 w-full resize-none rounded-2xl border border-border bg-background/60 px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
              />

              {jdText && (
                <div className="flex items-center justify-between">
                  <div className="flex gap-2 flex-wrap">
                    {jdText.split(/\W+/).filter(w => w.length > 4).slice(0, 5).map(k => (
                      <span key={k} className="rounded-full bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">{k}</span>
                    ))}
                  </div>
                  <LiquidGlassButton
                    tone="primary"
                    size="sm"
                    disabled={isAnalyzing}
                    onClick={() => {
                      setIsAnalyzing(true);
                      // Simulate analysis (TODO: wire to apiClient.resume.optimize)
                      setTimeout(() => setIsAnalyzing(false), 1500);
                    }}
                  >
                    {isAnalyzing ? "Analyzing…" : "Tailor Resume ✨"}
                  </LiquidGlassButton>
                </div>
              )}

              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <span>✓ Keyword matching</span>
                <span>✓ Bullet rewriting</span>
                <span>✓ Skills gap analysis</span>
              </div>
            </div>
          )}
        </motion.div>

        <motion.div variants={fadeUp} className="grid gap-6 lg:grid-cols-[300px_1fr_320px]">
          <aside className="space-y-6">
            <div className="rounded-3xl border border-border bg-card/60 p-6 text-center">
              <AtsScoreRing score={78} />
            </div>
            <KeywordCoverage
              matched={["React", "TypeScript", "Python", "FastAPI"]}
              missing={["AWS", "Docker", "CI/CD", "PostgreSQL"]}
            />
          </aside>

          <section className="rounded-3xl border border-border bg-card/40 p-6">
            <div className="text-sm text-muted-foreground">Preview</div>
            <div className="mt-3 aspect-[8.5/11] w-full overflow-hidden rounded-2xl border border-border bg-background p-8 text-sm">
              <div className="text-2xl font-medium">Your Name</div>
              <div className="mt-1 text-muted-foreground">Frontend Engineer · email@you.com · github.com/you</div>
              <div className="mt-6 text-xs uppercase tracking-wide text-muted-foreground">Experience</div>
              <p className="mt-2">Resume preview pane — bullets you accept appear here. Connect parser to populate.</p>
            </div>
          </section>

          <aside className="space-y-3">
            <div className="text-sm text-muted-foreground">AI suggestions</div>
            {suggestions.length === 0 ? (
              <EmptyState title="All suggestions reviewed" description="Re-run the Resume Agent to get more tailored bullets." />
            ) : (
              <SuggestionsList suggestions={suggestions} onAccept={accept} onReject={reject} />
            )}
          </aside>
        </motion.div>
        </>
      )}
    </motion.div>
  );
}
