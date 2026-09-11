"use client";

import { useState, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Upload, Download, Target, FileText, Wand2, CloudUpload, ChevronDown, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { CommandHeader } from "@/components/immersive/CommandHeader";
import { AtsScoreRing } from "@/components/resume/AtsScoreRing";
import { KeywordCoverage } from "@/components/resume/KeywordCoverage";
import { SuggestionsList, type Suggestion } from "@/components/resume/SuggestionsList";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiClient } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AtsData {
  matched_keywords: string[];
  missing_keywords: string[];
  suggestions: string[];
  warnings: string[];
  keyword_score: number;
  section_score: number;
  format_score: number;
}

interface ResumeDoc {
  id: string;
  filename: string;
  is_primary: boolean;
  ats_score: number | null;
  ats_data: AtsData | null;
}

interface OptimizeResult {
  run_id: string;
  status: string;
  template?: string;
  pdf_available?: boolean;
  pdf_document_id?: string | null;
  resume_markdown?: string;
  summary?: string;
  ats_score?: number | null;
  keywords_matched?: string[];
  keywords_missing?: string[];
  changes_made?: string[];
  warnings?: string[];
}

interface AgentRun {
  id: string;
  agent_type: string;
  status: "pending" | "running" | "completed" | "failed" | "awaiting_approval";
  created_at: string;
  pdf_available?: boolean;
  output?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MOCK_SUGGESTIONS: Suggestion[] = [
  {
    id: "1",
    original: "Worked on the backend team building REST APIs.",
    suggestion:
      "Designed and shipped 12 REST endpoints handling 4k+ daily requests; cut p95 latency from 320ms to 110ms.",
  },
  {
    id: "2",
    original: "Built a React dashboard.",
    suggestion:
      "Built a real-time React dashboard with TanStack Query and WebSockets, used daily by 200+ internal operators.",
  },
];

const COVER_LETTER_TONES = ["Professional", "Enthusiastic", "Concise", "Story-driven"] as const;
type CoverTone = (typeof COVER_LETTER_TONES)[number];

type TemplateId = "classic" | "modern" | "technical";

const RESUME_TEMPLATES: Array<{
  id: TemplateId;
  name: string;
  description: string;
  badge: string;
  preview: string[];
}> = [
  {
    id: "modern",
    name: "Modern",
    description: "Clean Helvetica, ATS-optimized for Greenhouse & Workday",
    badge: "Recommended",
    preview: [
      "Name",
      "Contact · LinkedIn",
      "─────────────────",
      "EXPERIENCE",
      "• Achieved X by doing Y",
      "EDUCATION",
      "• BS Computer Science",
    ],
  },
  {
    id: "classic",
    name: "Classic",
    description: "Times New Roman, conservative — passes Taleo & legacy ATS",
    badge: "Taleo-Safe",
    preview: [
      "Name",
      "email@you.com | LinkedIn",
      "WORK EXPERIENCE",
      "  Company Name",
      "  Job Title | 2022–2024",
      "EDUCATION",
    ],
  },
  {
    id: "technical",
    name: "Technical",
    description: "Skills-first layout for engineering & dev roles",
    badge: "Dev-Focused",
    preview: [
      "Name",
      "github.com/you | LinkedIn",
      "TECHNICAL SKILLS",
      "Python, FastAPI, React",
      "EXPERIENCE",
      "EDUCATION",
    ],
  },
];

// ---------------------------------------------------------------------------
// Cover Letter Generator (sub-component)
// ---------------------------------------------------------------------------

interface CoverLetterGeneratorProps {
  tone: CoverTone;
  setTone: (t: CoverTone) => void;
  jd: string;
  setJd: (v: string) => void;
  letter: string;
  setLetter: (v: string) => void;
  generating: boolean;
  onGenerate: () => void;
}

function CoverLetterGenerator({
  tone,
  setTone,
  jd,
  setJd,
  letter,
  setLetter,
  generating,
  onGenerate,
}: CoverLetterGeneratorProps) {
  const [showDriveMenu, setShowDriveMenu] = useState(false);

  const copyToClipboard = () => {
    if (letter) navigator.clipboard.writeText(letter);
  };

  const downloadPdf = () => {
    if (!letter) return;
    const blob = new Blob([letter], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "cover-letter.txt";
    a.click();
    URL.revokeObjectURL(url);
    toast.info("Tip: Open the file and print as PDF for a clean PDF format");
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
            onClick={onGenerate}
          >
            {generating ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Wand2 className="h-4 w-4" />
            )}
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
                onClick={downloadPdf}
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
                  <ChevronDown
                    className={`h-3 w-3 transition-transform ${showDriveMenu ? "rotate-180" : ""}`}
                  />
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
                      <button
                        onClick={() => { toast.info("Google Drive integration coming soon"); setShowDriveMenu(false); }}
                        className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-xs hover:bg-muted"
                      >
                        <CloudUpload className="h-3.5 w-3.5 text-muted-foreground" />
                        Save to Google Drive
                      </button>
                      <button
                        onClick={() => { toast.info("Google Docs integration coming soon"); setShowDriveMenu(false); }}
                        className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-xs hover:bg-muted"
                      >
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
  );
}

// ---------------------------------------------------------------------------
// Template cards (inline, wired to selectedTemplate state)
// ---------------------------------------------------------------------------

interface TemplateSelectorProps {
  selected: TemplateId;
  onSelect: (id: TemplateId) => void;
  onTailor: () => void;
  isTailoring: boolean;
}

function TemplateSelector({ selected, onSelect, onTailor, isTailoring }: TemplateSelectorProps) {
  return (
    <div className="space-y-6">
      <div>
        <div className="text-sm text-muted-foreground">Resume Workspace · Templates</div>
        <h2 className="mt-1 text-xl font-medium">Choose a template.</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          All templates are single-column and optimised for Applicant Tracking Systems.
        </p>
      </div>

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {RESUME_TEMPLATES.map((tpl) => {
          const isSelected = selected === tpl.id;
          return (
            <div
              key={tpl.id}
              className={`rounded-3xl border p-6 transition-colors ${
                isSelected ? "border-primary bg-primary/5" : "border-border bg-card/60"
              }`}
            >
              {/* Mini text preview */}
              <div className="h-48 w-full overflow-hidden rounded-2xl border border-border bg-background p-4 font-mono text-[10px] leading-relaxed text-muted-foreground">
                {tpl.preview.map((line, i) => (
                  <div key={i} className={i === 0 ? "font-semibold text-foreground text-xs" : ""}>
                    {line}
                  </div>
                ))}
              </div>

              <div className="mt-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{tpl.name}</span>
                  <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                    {tpl.badge}
                  </span>
                </div>

                <p className="text-sm text-muted-foreground">{tpl.description}</p>

                <div className="flex items-center justify-between pt-1">
                  <LiquidGlassButton
                    tone={isSelected ? "ghost" : "primary"}
                    size="sm"
                    onClick={() => onSelect(tpl.id)}
                  >
                    {isSelected ? "Selected ✓" : "Select"}
                  </LiquidGlassButton>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-3">
        <LiquidGlassButton tone="primary" size="sm" onClick={onTailor} disabled={isTailoring}>
          {isTailoring ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Wand2 className="h-4 w-4" />
          )}
          {isTailoring ? "Tailoring…" : `Tailor with ${RESUME_TEMPLATES.find((t) => t.id === selected)?.name ?? selected} template`}
        </LiquidGlassButton>
        <span className="text-xs text-muted-foreground">
          Uses the job description from the Builder tab
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// History tab
// ---------------------------------------------------------------------------

interface HistoryTabProps {
  agentRuns: AgentRun[] | undefined;
  isLoading: boolean;
  onDownload: (runId: string) => void;
}

function HistoryTab({ agentRuns, isLoading, onDownload }: HistoryTabProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground gap-2">
        <Loader2 className="h-5 w-5 animate-spin" />
        Loading history…
      </div>
    );
  }

  if (!agentRuns || agentRuns.length === 0) {
    return (
      <EmptyState
        title="Resume history"
        description="Previous tailoring runs will appear here once you tailor your first resume."
      />
    );
  }

  const statusColors: Record<AgentRun["status"], string> = {
    pending: "bg-muted text-muted-foreground",
    running: "bg-primary/10 text-primary",
    completed: "bg-success/15 text-success",
    failed: "bg-destructive/15 text-destructive",
    awaiting_approval: "bg-warning/15 text-warning",
  };

  return (
    <div className="space-y-3">
      {agentRuns.map((run) => (
        <div
          key={run.id}
          className="flex items-center justify-between rounded-3xl border border-border bg-card/60 px-5 py-4"
        >
          <div className="space-y-1">
            <div className="text-sm font-medium">Resume Agent Run</div>
            <div className="text-xs text-muted-foreground">
              {new Date(run.created_at).toLocaleString(undefined, {
                dateStyle: "medium",
                timeStyle: "short",
              })}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusColors[run.status] ?? "bg-muted text-muted-foreground"}`}
            >
              {run.status.replace("_", " ")}
            </span>
            {(run.output?.pdf_document_id as string | undefined) && (
              <button
                onClick={() => onDownload(run.output?.pdf_document_id as string)}
                className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-card transition-colors"
              >
                <Download className="h-3.5 w-3.5" />
                PDF
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ResumePage() {
  const queryClient = useQueryClient();

  // UI state
  const [tab, setTab] = useState<"builder" | "templates" | "history" | "cover-letter">("builder");
  const [jdText, setJdText] = useState("");
  const [jdPanelOpen, setJdPanelOpen] = useState(true);
  const [showExportMenu, setShowExportMenu] = useState(false);

  // Resume upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadedDocId, setUploadedDocId] = useState<string | null>(null);

  // Optimize / tailor state
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateId>("modern");
  const [lastDocId, setLastDocId] = useState<string | null>(null);
  const [lastAtsScore, setLastAtsScore] = useState<number | null>(null);
  const [lastMissingKeywords, setLastMissingKeywords] = useState<string[]>([]);
  const [lastWarnings, setLastWarnings] = useState<string[]>([]);
  const [resumePreviewText, setResumePreviewText] = useState<string | null>(null);

  // Suggestions state
  const [suggestions, setSuggestions] = useState<Suggestion[]>(MOCK_SUGGESTIONS);

  // Cover letter state (lifted so CoverLetterGenerator is stateless)
  const [coverJd, setCoverJd] = useState("");
  const [coverTone, setCoverTone] = useState<CoverTone>("Professional");
  const [coverLetter, setCoverLetter] = useState("");
  const [generating, setGenerating] = useState(false);

  // -------------------------------------------------------------------------
  // Query: resume documents (polls while ATS score is computing)
  // -------------------------------------------------------------------------
  const { data: resumeDocs, isLoading: docsLoading } = useQuery<ResumeDoc[]>({
    queryKey: ["resume-docs"],
    queryFn: async () => {
      const { data } = await apiClient.get("/rag/documents?doc_type=resume");
      return data as ResumeDoc[];
    },
    refetchInterval: (query) => {
      const docs = query.state.data;
      const primary = docs?.find((d) => d.is_primary);
      return primary && primary.ats_score === null ? 3000 : false;
    },
  });

  const primaryDoc = resumeDocs?.find((d) => d.is_primary) ?? resumeDocs?.[0] ?? null;
  const atsScore = primaryDoc?.ats_score ?? null;
  const atsData = primaryDoc?.ats_data ?? null;
  const matchedKeywords = atsData?.matched_keywords ?? [];
  const missingKeywords = atsData?.missing_keywords ?? [];

  const aiSuggestions: Suggestion[] = (atsData?.suggestions ?? []).map((s, i) => ({
    id: String(i),
    original: "",
    suggestion: s,
  }));

  // Use AI suggestions if available, otherwise fall back to MOCK
  const activeSuggestions = aiSuggestions.length > 0 ? suggestions : MOCK_SUGGESTIONS;

  // -------------------------------------------------------------------------
  // Query: agent runs for history tab
  // -------------------------------------------------------------------------
  const { data: agentRuns, isLoading: runsLoading } = useQuery<AgentRun[]>({
    queryKey: ["agent-runs", "resume"],
    queryFn: async () => {
      const { data } = await apiClient.get("/agents/runs?limit=20");
      return ((Array.isArray(data) ? data : data.runs ?? []) as AgentRun[]).filter((r) => ["resume", "resume_optimize"].includes(r.agent_type));
    },
    enabled: tab === "history",
  });

  // -------------------------------------------------------------------------
  // Mutation: optimize/tailor resume
  // -------------------------------------------------------------------------
  const optimizeMutation = useMutation<OptimizeResult, Error, string>({
    mutationFn: async (jdInput: string) => {
      const { data } = await apiClient.post("/resume/optimize", {
        jd_text: jdInput,
        template: selectedTemplate,
      });
      return data as OptimizeResult;
    },
    onSuccess: (data) => {
      if (data.resume_markdown) setResumePreviewText(data.resume_markdown);
      if (data.pdf_document_id) setLastDocId(data.pdf_document_id);
      setLastAtsScore(data.ats_score ?? null);
      setLastMissingKeywords(data.keywords_missing ?? []);
      setLastWarnings(data.warnings ?? []);
      toast.success(
        data.ats_score != null
          ? `Resume tailored! ATS score ${data.ats_score}. Review the preview below.`
          : "Resume tailored! Review the preview below."
      );
      queryClient.invalidateQueries({ queryKey: ["resume-docs"] });
      queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
    },
    onError: () => toast.error("Optimization failed — check model settings"),
  });

  // -------------------------------------------------------------------------
  // Mutation: save resume to the user's Google Drive
  // -------------------------------------------------------------------------
  const saveToDriveMutation = useMutation<
    { id: string; name: string; web_view_link?: string },
    Error,
    string
  >({
    mutationFn: async (docId: string) => {
      const { data } = await apiClient.post(`/rag/documents/${docId}/save-to-drive`);
      return data as { id: string; name: string; web_view_link?: string };
    },
    onSuccess: (data) => {
      if (data.web_view_link) {
        toast.success("Saved to Google Drive", {
          action: { label: "Open", onClick: () => window.open(data.web_view_link, "_blank") },
        });
      } else {
        toast.success(`Saved ${data.name} to Google Drive`);
      }
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail || "Could not save to Drive — connect Google in Settings");
    },
  });

  // -------------------------------------------------------------------------
  // File upload handler
  // -------------------------------------------------------------------------
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("doc_type", "resume");
      fd.append("is_primary", "true");
      const { data } = await apiClient.post("/rag/upload", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setUploadedDocId((data as { id: string }).id);
      toast.success(`Resume uploaded: ${file.name}`);
      if ((data as { warning?: string }).warning) {
        toast.warning((data as { warning: string }).warning);
      }
      queryClient.invalidateQueries({ queryKey: ["resume-docs"] });
    } catch {
      toast.error("Upload failed — try a PDF or DOCX file");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // -------------------------------------------------------------------------
  // PDF download handler
  // -------------------------------------------------------------------------
  const handleDownloadPdf = async (documentId?: string) => {
    const id = documentId ?? lastDocId;
    if (!id) {
      toast.info("Tailor your resume first to generate a PDF");
      return;
    }
    try {
      const response = await apiClient.get(`/resume/download/${id}`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(
        new Blob([response.data as BlobPart], { type: "application/pdf" })
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = "resume.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Download failed");
    }
  };

  // -------------------------------------------------------------------------
  // Cover letter generation
  // -------------------------------------------------------------------------
  const generateCoverLetter = async () => {
    setGenerating(true);
    // Map UI tone labels to backend VALID_TONES (formal | casual | bold)
    const toneMap: Record<CoverTone, "formal" | "casual" | "bold"> = {
      Professional: "formal",
      Concise: "formal",
      Enthusiastic: "casual",
      "Story-driven": "bold",
    };
    try {
      // Call the real cover-letter endpoint, which runs the cover_letter agent
      // synchronously and returns the generated content.
      const { data } = await apiClient.post<{
        run_id: string;
        status: string;
        content: string | null;
        tone: string | null;
      }>("/cover-letter/generate", {
        tone: toneMap[coverTone],
        jd_text: coverJd || undefined,
      });

      if (data.content) {
        setCoverLetter(data.content);
        toast.success("Cover letter generated");
      } else {
        toast.error("No cover letter content returned — check model settings");
      }
    } catch {
      toast.error("Cover letter generation failed — check model settings");
    } finally {
      setGenerating(false);
    }
  };

  // -------------------------------------------------------------------------
  // Suggestion handlers
  // -------------------------------------------------------------------------
  const acceptSuggestion = (id: string) =>
    setSuggestions((s) => s.filter((x) => x.id !== id));
  const rejectSuggestion = (id: string) =>
    setSuggestions((s) => s.filter((x) => x.id !== id));

  // When AI suggestions come in, merge them in (avoiding dupes)
  const displayedSuggestions: Suggestion[] =
    aiSuggestions.length > 0 ? aiSuggestions : activeSuggestions;

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      <CommandHeader
        eyebrow="HR SaaS Hero"
        title="Tailor your resume."
        description="Paste a target job, scan keywords, improve bullets, and export once your preview is ready."
        actions={
        <div className="flex flex-wrap gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.doc,.docx"
            className="hidden"
            onChange={handleFileChange}
          />
          <LiquidGlassButton
            tone="ghost"
            size="sm"
            disabled={uploading}
            onClick={() => fileInputRef.current?.click()}
          >
            {uploading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            {uploading ? "Uploading…" : "Upload"}
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
                  <button
                    disabled={saveToDriveMutation.isPending}
                    onClick={() => {
                      setShowExportMenu(false);
                      if (!primaryDoc?.id) {
                        toast.info("Upload a resume first, then save it to Drive");
                        return;
                      }
                      saveToDriveMutation.mutate(primaryDoc.id);
                    }}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm hover:bg-muted disabled:opacity-60"
                  >
                    {saveToDriveMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                    ) : (
                      <CloudUpload className="h-4 w-4 text-muted-foreground" />
                    )}
                    {saveToDriveMutation.isPending ? "Saving…" : "Save to Google Drive"}
                  </button>
                  <button
                    onClick={() => { toast.info("Google Docs integration coming soon"); setShowExportMenu(false); }}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm hover:bg-muted"
                  >
                    <FileText className="h-4 w-4 text-muted-foreground" /> Save as Google Doc
                  </button>
                  <button
                    onClick={() => {
                      setShowExportMenu(false);
                      handleDownloadPdf();
                    }}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm hover:bg-muted"
                  >
                    <Download className="h-4 w-4 text-muted-foreground" /> Download PDF
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <LiquidGlassButton
            tone="primary"
            size="sm"
            onClick={() => handleDownloadPdf()}
            disabled={!lastDocId}
            title={lastDocId ? "Download tailored PDF" : "Tailor your resume first to generate a PDF"}
          >
            <Download className="h-4 w-4" /> Export
          </LiquidGlassButton>
        </div>
        }
      />

      {/* Tab nav */}
      <motion.div variants={fadeUp}>
        <div className="flex gap-1 rounded-full border border-border bg-muted/40 p-1 text-sm">
          {(["builder", "templates", "history"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-full px-4 py-1.5 capitalize transition-colors ${
                tab === t
                  ? "bg-background shadow-sm text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Templates tab */}
      {tab === "templates" && (
        <motion.div variants={fadeUp}>
          <TemplateSelector
            selected={selectedTemplate}
            onSelect={setSelectedTemplate}
            onTailor={() => optimizeMutation.mutate(jdText)}
            isTailoring={optimizeMutation.isPending}
          />
        </motion.div>
      )}

      {/* History tab */}
      {tab === "history" && (
        <motion.div variants={fadeUp}>
          <HistoryTab
            agentRuns={agentRuns}
            isLoading={runsLoading}
            onDownload={handleDownloadPdf}
          />
        </motion.div>
      )}

      {/* Builder tab */}
      {tab === "builder" && (
        <>
          {/* JD panel */}
          <motion.div
            variants={fadeUp}
            className="rounded-3xl border border-border bg-card/60 p-6"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Target className="h-5 w-5 text-primary" />
                <div className="font-medium">Target Job Description</div>
                {jdText && (
                  <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                    Active
                  </span>
                )}
              </div>
              <LiquidGlassButton
                tone="ghost"
                size="sm"
                onClick={() => setJdPanelOpen(!jdPanelOpen)}
              >
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
                      {jdText
                        .split(/\W+/)
                        .filter((w) => w.length > 4)
                        .slice(0, 5)
                        .map((k) => (
                          <span
                            key={k}
                            className="rounded-full bg-secondary px-2 py-0.5 text-xs text-secondary-foreground"
                          >
                            {k}
                          </span>
                        ))}
                    </div>
                    <LiquidGlassButton
                      tone="primary"
                      size="sm"
                      disabled={optimizeMutation.isPending}
                      onClick={() => optimizeMutation.mutate(jdText)}
                    >
                      {optimizeMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : null}
                      {optimizeMutation.isPending ? "Tailoring…" : "Tailor Resume ✨"}
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

          {/* Main builder grid */}
          <motion.div
            variants={fadeUp}
            className="grid gap-6 lg:grid-cols-[300px_1fr_320px]"
          >
            {/* Left aside: ATS score + keyword coverage */}
            <aside className="space-y-6">
              <div className="rounded-3xl border border-border bg-card/60 p-6 text-center">
                {docsLoading || (primaryDoc && atsScore === null) ? (
                  <div className="flex flex-col items-center justify-center gap-3 py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <div className="text-xs text-muted-foreground">
                      {docsLoading ? "Loading…" : "Computing ATS score…"}
                    </div>
                  </div>
                ) : (
                  <AtsScoreRing score={atsScore ?? 0} />
                )}
                {primaryDoc && (
                  <div className="mt-3 text-xs text-muted-foreground truncate px-2">
                    {primaryDoc.filename}
                  </div>
                )}
                {!primaryDoc && !docsLoading && (
                  <div className="mt-3 text-xs text-muted-foreground">
                    Upload a resume to see your ATS score
                  </div>
                )}
              </div>

              <KeywordCoverage
                matched={
                  matchedKeywords.length > 0
                    ? matchedKeywords
                    : ["React", "TypeScript", "Python", "FastAPI"]
                }
                missing={
                  missingKeywords.length > 0
                    ? missingKeywords
                    : ["AWS", "Docker", "CI/CD", "PostgreSQL"]
                }
              />
            </aside>

            {/* Center: resume preview */}
            <section className="rounded-3xl border border-border bg-card/40 p-6">
              <div className="text-sm text-muted-foreground">Preview</div>
              {lastAtsScore != null && (
                <div className="mt-1 text-xs text-muted-foreground">
                  Tailored ATS score: <span className="font-medium text-foreground">{lastAtsScore}</span>
                  {lastMissingKeywords.length > 0 &&
                    ` · missing: ${lastMissingKeywords.slice(0, 5).join(", ")}`}
                </div>
              )}
              {lastWarnings.length > 0 && (
                <div className="mt-1 text-xs text-warning">
                  {lastWarnings.slice(0, 2).join(" ")}
                </div>
              )}
              <div className="mt-3 aspect-[8.5/11] w-full overflow-hidden rounded-2xl border border-border bg-background p-8 text-sm">
                {resumePreviewText ? (
                  <pre className="whitespace-pre-wrap text-sm font-sans leading-relaxed text-foreground">
                    {resumePreviewText}
                  </pre>
                ) : (
                  <>
                    <div className="text-2xl font-medium">Your Name</div>
                    <div className="mt-1 text-muted-foreground">
                      Frontend Engineer · email@you.com · github.com/you
                    </div>
                    <div className="mt-6 text-xs uppercase tracking-wide text-muted-foreground">
                      Experience
                    </div>
                    <p className="mt-2">
                      Resume preview pane — bullets you accept appear here. Upload a resume or tailor
                      it to see the preview.
                    </p>
                  </>
                )}
              </div>
            </section>

            {/* Right aside: AI suggestions */}
            <aside className="space-y-3">
              <div className="text-sm text-muted-foreground">AI suggestions</div>
              {displayedSuggestions.length === 0 ? (
                <EmptyState
                  title="All suggestions reviewed"
                  description="Re-run the Resume Agent to get more tailored bullets."
                />
              ) : (
                <SuggestionsList
                  suggestions={displayedSuggestions}
                  onAccept={acceptSuggestion}
                  onReject={rejectSuggestion}
                />
              )}
            </aside>
          </motion.div>
        </>
      )}

      {/* Suppress unused variable warning for uploadedDocId */}
      {uploadedDocId && null}
    </motion.div>
  );
}
