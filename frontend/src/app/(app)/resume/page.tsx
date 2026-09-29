"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Upload, Download, Target, FileText, Wand2, CloudUpload, Loader2, Pencil, FolderOpen } from "lucide-react";
import { toast } from "sonner";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { CommandHeader } from "@/components/immersive/CommandHeader";
import { AtsScoreRing } from "@/components/resume/AtsScoreRing";
import { KeywordCoverage } from "@/components/resume/KeywordCoverage";
import { SuggestionsList } from "@/components/resume/SuggestionsList";
import { ResumePreview } from "@/components/resume/ResumePreview";
import { ResumeFixPanel } from "@/components/resume/ResumeFixPanel";
import { SAMPLE_RESUME_MARKDOWN } from "@/components/resume/sample-resume";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiClient, getApiErrorMessage } from "@/lib/api";
import { getResumeInsightData } from "@/lib/resume-insights";
import { takePendingJd } from "@/lib/job-handoff";
import type {
  ContactFields,
  ResumeFixPayload,
  ResumeOptimizeResponse,
  ResumeReview,
  ResumeTemplateId,
  TailoredResume,
} from "@/lib/resume-types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AtsData {
  matched_keywords: string[];
  missing_keywords: string[];
  suggestions: string[];
  warnings: string[];
  keyword_score: number | null;
  readability_score?: number;
  format_score: number;
}

interface ResumeDoc {
  id: string;
  filename: string;
  is_primary: boolean;
  ats_score: number | null;
  ats_data: AtsData | null;
}

/** POST /resume/optimize response (includes review + contact_suggestions). */
type OptimizeResult = ResumeOptimizeResponse;

interface JobAtsAnalysis {
  composite_score: number;
  matched_keywords: string[];
  missing_keywords: string[];
  suggestions: string[];
}

interface AgentRun {
  id: string;
  agent_type: string;
  status: "pending" | "running" | "completed" | "failed" | "awaiting_approval";
  started_at: string;
  pdf_available?: boolean;
  output?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COVER_LETTER_TONES = ["Professional", "Enthusiastic", "Concise", "Story-driven"] as const;
type CoverTone = (typeof COVER_LETTER_TONES)[number];

type TemplateId = ResumeTemplateId;

const RESUME_TEMPLATES: Array<{
  id: TemplateId;
  name: string;
  description: string;
  badge: string;
}> = [
  {
    id: "modern",
    name: "Modern",
    description: "Arial-style sans, centered navy header, accent rules",
    badge: "Recommended",
  },
  {
    id: "classic",
    name: "Classic",
    description: "Times serif, black and white, the most conservative ATS choice",
    badge: "Taleo-Safe",
  },
  {
    id: "technical",
    name: "Technical",
    description: "Compact sans with teal accents, fits dense skills and projects on one page",
    badge: "Dev-Focused",
  },
];

/** Scale for template-card thumbnails (816px letter page → ~245px wide). */
const TEMPLATE_THUMB_SCALE = 0.3;

/** Backend limit for a manual markdown edit. */
const MAX_MARKDOWN_LENGTH = 30_000;

function isTemplateId(value: unknown): value is TemplateId {
  return value === "modern" || value === "classic" || value === "technical";
}

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
  const copyToClipboard = () => {
    if (letter) void navigator.clipboard.writeText(letter).then(() => toast.success("Copied"), () => toast.error("Could not copy"));
  };

  const downloadText = () => {
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
            <span className="text-xs text-muted-foreground">(required)</span>
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
            disabled={generating || !jd.trim()}
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
                onClick={downloadText}
                className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:bg-card transition-colors"
              >
                Download text
              </button>
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
  canTailor: boolean;
}

function TemplateSelector({ selected, onSelect, onTailor, isTailoring, canTailor }: TemplateSelectorProps) {
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
              {/* Thumbnail rendered with the same layout as the PDF template */}
              <div
                aria-hidden="true"
                className="pointer-events-none flex h-48 w-full select-none justify-center overflow-hidden rounded-2xl border border-border bg-muted/40 pt-3"
              >
                <ResumePreview
                  markdown={SAMPLE_RESUME_MARKDOWN}
                  template={tpl.id}
                  scale={TEMPLATE_THUMB_SCALE}
                />
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
        <LiquidGlassButton tone="primary" size="sm" onClick={onTailor} disabled={isTailoring || !canTailor}>
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
  onOpen: (documentId: string) => void;
  /** Document id currently being opened, if any. */
  openingId: string | null;
}

function HistoryTab({ agentRuns, isLoading, onDownload, onOpen, openingId }: HistoryTabProps) {
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
    failed: "bg-danger/15 text-danger",
    awaiting_approval: "bg-warning/15 text-warning",
  };

  return (
    <div className="space-y-3">
      {agentRuns.map((run) => {
        const docId = typeof run.output?.pdf_document_id === "string" ? run.output.pdf_document_id : null;
        const isOpening = docId !== null && openingId === docId;
        return (
          <div
            key={run.id}
            className="flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-border bg-card/60 px-5 py-4"
          >
            <div className="space-y-1">
              <div className="text-sm font-medium">Resume Agent Run</div>
              <div className="text-xs text-muted-foreground">
                {new Date(run.started_at).toLocaleString(undefined, {
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
              {docId && (
                <>
                  <button
                    type="button"
                    onClick={() => onOpen(docId)}
                    disabled={openingId !== null}
                    aria-label="Open this tailored resume in the builder"
                    className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-card transition-colors disabled:opacity-60"
                  >
                    {isOpening ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <FolderOpen className="h-3.5 w-3.5" />
                    )}
                    {isOpening ? "Opening…" : "Open"}
                  </button>
                  <button
                    type="button"
                    onClick={() => onDownload(docId)}
                    aria-label="Download this tailored resume as PDF"
                    className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-card transition-colors"
                  >
                    <Download className="h-3.5 w-3.5" />
                    PDF
                  </button>
                </>
              )}
            </div>
          </div>
        );
      })}
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

  // Picks up a job description handed off from the Jobs page's "Tailor
  // resume for this job" action, so the user lands here with it prefilled.
  useEffect(() => {
    const pending = takePendingJd();
    if (pending?.jdText) {
      setJdText(pending.jdText);
      setJdPanelOpen(true);
      setTab("builder");
      toast.info(`Job description loaded from ${pending.role} at ${pending.company}`);
    }
  }, []);

  // Resume upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  // Optimize / tailor state
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateId>("modern");
  const [lastDocId, setLastDocId] = useState<string | null>(null);
  const [lastAtsScore, setLastAtsScore] = useState<number | null>(null);
  const [lastMissingKeywords, setLastMissingKeywords] = useState<string[]>([]);
  const [lastWarnings, setLastWarnings] = useState<string[]>([]);
  const [resumePreviewText, setResumePreviewText] = useState<string | null>(null);
  const [lastReview, setLastReview] = useState<ResumeReview | null>(null);
  const [contactSuggestions, setContactSuggestions] = useState<Partial<ContactFields>>({});
  /** Template the current tailored document was rendered with. */
  const [lastTemplate, setLastTemplate] = useState<TemplateId | null>(null);
  const [aiChanges, setAiChanges] = useState<string[]>([]);
  const [aiSummary, setAiSummary] = useState<string | null>(null);
  const [jobAts, setJobAts] = useState<{ documentId: string; jdText: string; data: JobAtsAnalysis } | null>(null);

  // Manual markdown edit of the tailored resume
  const [editingText, setEditingText] = useState(false);
  const [draftMarkdown, setDraftMarkdown] = useState("");

  // Cover letter state (lifted so CoverLetterGenerator is stateless)
  const [coverJd, setCoverJd] = useState("");
  const [coverTone, setCoverTone] = useState<CoverTone>("Professional");
  const [coverLetter, setCoverLetter] = useState("");
  const [generating, setGenerating] = useState(false);

  // -------------------------------------------------------------------------
  // Query: resume documents (polls while ATS score is computing)
  // -------------------------------------------------------------------------
  const { data: resumeDocs, isLoading: docsLoading, isError: docsError } = useQuery<ResumeDoc[]>({
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
  const activeJobAts = jobAts && jobAts.documentId === primaryDoc?.id && jobAts.jdText === jdText.trim() ? jobAts.data : null;
  const insightData = getResumeInsightData(activeJobAts, primaryDoc);

  const atsMutation = useMutation<JobAtsAnalysis, Error, { documentId: string; jdText: string }>({
    mutationFn: async ({ documentId, jdText: description }) => {
      const { data } = await apiClient.post("/resume/ats-score", { document_id: documentId, jd_text: description });
      return data as JobAtsAnalysis;
    },
    onSuccess: (data, variables) => setJobAts({ ...variables, data }),
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail || "Could not analyze this resume and job description");
    },
  });

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
  // Tailored document: apply a server snapshot (fix / template / open)
  // -------------------------------------------------------------------------
  const applyTailored = (r: TailoredResume) => {
    setResumePreviewText(r.resume_markdown);
    setLastReview(r.review);
    setLastWarnings(r.warnings ?? []);
    setLastAtsScore(r.ats_score ?? null);
    setLastMissingKeywords(r.keywords_missing ?? []);
    setLastTemplate(isTemplateId(r.template) ? r.template : null);
    setContactSuggestions(r.contact_suggestions ?? {});
    setLastDocId(r.document_id);
    setAiChanges(r.changes_made ?? []);
    setAiSummary(r.summary ?? null);
    queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
  };

  const postFix = async (documentId: string, payload: ResumeFixPayload) => {
    // Re-renders the PDF server-side; allow more than the default 30s.
    const { data } = await apiClient.post(`/resume/tailored/${documentId}/fix`, payload, { timeout: 60_000 });
    return data as TailoredResume;
  };

  const templateMutation = useMutation<TailoredResume, unknown, TemplateId>({
    mutationFn: async (template) => {
      if (!lastDocId) throw new Error("Tailor your resume first.");
      return postFix(lastDocId, { template });
    },
    onSuccess: (data, template) => {
      applyTailored(data);
      setSelectedTemplate(template);
      toast.success(`Switched to the ${RESUME_TEMPLATES.find((t) => t.id === template)?.name ?? template} template`);
    },
    onError: (err) => toast.error(getApiErrorMessage(err, "Could not switch the template")),
  });

  const editTextMutation = useMutation<TailoredResume, unknown, string>({
    mutationFn: async (markdown) => {
      if (!lastDocId) throw new Error("Tailor your resume first.");
      return postFix(lastDocId, { resume_markdown: markdown });
    },
    onSuccess: (data) => {
      applyTailored(data);
      setEditingText(false);
      toast.success("Resume updated");
    },
    onError: (err) => toast.error(getApiErrorMessage(err, "Could not save your changes")),
  });

  const openTailoredMutation = useMutation<TailoredResume, unknown, string>({
    mutationFn: async (documentId) => {
      const { data } = await apiClient.get(`/resume/tailored/${documentId}`);
      return data as TailoredResume;
    },
    onSuccess: (data) => {
      setEditingText(false);
      applyTailored(data);
      setTab("builder");
    },
    onError: (err) => toast.error(getApiErrorMessage(err, "Could not open this resume")),
  });

  const startEditingText = () => {
    setDraftMarkdown(resumePreviewText ?? "");
    setEditingText(true);
  };

  const cancelEditingText = () => {
    setDraftMarkdown(resumePreviewText ?? "");
    setEditingText(false);
  };

  // -------------------------------------------------------------------------
  // Mutation: optimize/tailor resume
  // -------------------------------------------------------------------------
  const optimizeMutation = useMutation<OptimizeResult, Error, string>({
    mutationFn: async (jdInput: string) => {
      const jd = jdInput.trim();
      if (!jd) throw new Error("Paste the job description before tailoring your resume.");
      // This call runs the LLM synchronously server-side (no SSE/queue) and
      // routinely takes 30-60s+ — well past the client's default 30s timeout,
      // which would abort a request the backend was about to complete.
      const { data } = await apiClient.post("/resume/optimize", {
        jd_text: jd,
        template: selectedTemplate,
      }, { timeout: 120_000 });
      return data as OptimizeResult;
    },
    onSuccess: async (data) => {
      if (data.resume_markdown) setResumePreviewText(data.resume_markdown);
      // A new run replaces the previous document; without a stored PDF there
      // is nothing to fix or download, so don't keep pointing at the old one.
      setLastDocId(data.pdf_document_id ?? null);
      setLastReview(data.review ?? null);
      setContactSuggestions(data.contact_suggestions ?? {});
      setLastTemplate(isTemplateId(data.template) ? data.template : selectedTemplate);
      setEditingText(false);
      setAiChanges(data.changes_made ?? []);
      setAiSummary(data.summary ?? null);
      setLastAtsScore(data.ats_score ?? null);
      setLastMissingKeywords(data.keywords_missing ?? []);
      setLastWarnings(data.warnings ?? []);
      if (data.resume_markdown && data.run_id) {
        await apiClient.post(`/agents/${data.run_id}/approve`, { approved: true });
      }
      const reviewIssues = data.review?.issues.length ?? 0;
      if (reviewIssues > 0) toast.warning(`Resume tailored — ${reviewIssues} detail(s) need your input below.`);
      else if (data.warnings?.length) toast.warning(data.warnings[0]);
      else toast.success(data.ats_score != null ? `Resume tailored! ATS score ${data.ats_score}.` : "Resume tailored.");
      queryClient.invalidateQueries({ queryKey: ["resume-docs"] });
      queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
    },
    onError: (err: unknown) => {
      const apiError = err as { message?: string; response?: { status?: number; data?: { detail?: string } } };
      const detail = apiError.response?.data?.detail;
      if (detail === "jd_text cannot be empty") {
        toast.error("Paste the full job description before tailoring your resume.");
      } else if (apiError.response?.status === 500 || detail === "Agent failed") {
        toast.error("We couldn’t tailor your resume. Please try again; if it keeps happening, contact support.");
      } else {
        toast.error(detail || apiError.message || "We couldn’t tailor your resume. Please try again.");
      }
    },
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
      setLastDocId(null);
      setResumePreviewText(null);
      setLastReview(null);
      setContactSuggestions({});
      setLastTemplate(null);
      setLastWarnings([]);
      setLastAtsScore(null);
      setLastMissingKeywords([]);
      setEditingText(false);
      setAiChanges([]);
      setAiSummary(null);
      setJobAts(null);
      toast.success(`Resume uploaded: ${file.name}`);
      if ((data as { warning?: string }).warning) {
        toast.warning((data as { warning: string }).warning);
      }
      queryClient.invalidateQueries({ queryKey: ["resume-docs"] });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail || "Upload failed — try a PDF or DOCX file");
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
        jd_text: coverJd.trim(),
      });

      if (data.content) {
        setCoverLetter(data.content);
        await apiClient.post(`/agents/${data.run_id}/approve`, { approved: true });
        toast.success("Cover letter generated");
      } else {
        toast.error("No cover letter content returned — check model settings");
      }
    } catch (error: unknown) {
      const apiError = error as { response?: { status?: number } };
      if (apiError.response?.status === 400) {
        toast.error("Add a job description before generating your cover letter.");
      } else if (apiError.response?.status === 504) {
        toast.error("Cover letter generation timed out. Please try again.");
      } else {
        toast.error("We couldn’t generate a cover letter. Check your active AI model in Settings and try again.");
      }
    } finally {
      setGenerating(false);
    }
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      <CommandHeader
        eyebrow="Resume workspace"
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
                      const docId = lastDocId ?? primaryDoc?.id;
                      if (!docId) {
                        toast.info("Upload a resume first, then save it to Drive");
                        return;
                      }
                      saveToDriveMutation.mutate(docId);
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
        <div className="flex gap-1 overflow-x-auto rounded-full border border-border bg-muted/40 p-1 text-sm">
          {(["builder", "templates", "history", "cover-letter"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`shrink-0 whitespace-nowrap rounded-full px-4 py-1.5 capitalize transition-colors ${
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
            canTailor={!!primaryDoc && !!jdText.trim()}
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
            onOpen={(id) => openTailoredMutation.mutate(id)}
            openingId={openTailoredMutation.isPending ? (openTailoredMutation.variables ?? null) : null}
          />
        </motion.div>
      )}

      {tab === "cover-letter" && <motion.div variants={fadeUp}><CoverLetterGenerator tone={coverTone} setTone={setCoverTone} jd={coverJd} setJd={setCoverJd} letter={coverLetter} setLetter={setCoverLetter} generating={generating} onGenerate={generateCoverLetter} /></motion.div>}

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

                {jdText.trim() && (
                  <div className="flex items-center justify-between">
                    <div className="flex gap-2">
                      <LiquidGlassButton tone="ghost" size="sm" disabled={!primaryDoc || atsMutation.isPending} onClick={() => primaryDoc && atsMutation.mutate({ documentId: primaryDoc.id, jdText: jdText.trim() })}>
                        {atsMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                        {atsMutation.isPending ? "Analyzing…" : "Analyze match"}
                      </LiquidGlassButton>
                      <LiquidGlassButton tone="primary" size="sm" disabled={!primaryDoc || optimizeMutation.isPending} onClick={() => optimizeMutation.mutate(jdText)}>
                        {optimizeMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                        {optimizeMutation.isPending ? "Tailoring…" : "Tailor Resume ✨"}
                      </LiquidGlassButton>
                    </div>
                  </div>
                )}

                {docsError && <p role="alert" className="text-sm text-danger">Could not load your resumes. Refresh the page and try again.</p>}
                {!primaryDoc && !docsLoading && <p className="text-sm text-muted-foreground">Upload a resume before analyzing or tailoring it.</p>}

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
                {docsLoading ? (
                  <div className="flex flex-col items-center justify-center gap-3 py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <div className="text-xs text-muted-foreground">
                      Loading resume…
                    </div>
                  </div>
                ) : (
                  insightData.score != null ? <AtsScoreRing score={insightData.score} /> : <div className="py-10 text-sm text-muted-foreground">Upload a resume to calculate its score</div>
                )}
                {insightData.score != null && <div className="text-xs text-muted-foreground">{insightData.scoreLabel}{activeJobAts ? " for this job" : " · run Analyze match for job-specific results"}</div>}
                {docsError && <div role="alert" className="mt-3 text-xs text-danger">Could not load your resume.</div>}
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

              {activeJobAts ? <KeywordCoverage matched={insightData.matched} missing={insightData.missing} /> : <div className="rounded-3xl border border-border bg-card/60 p-5 text-sm text-muted-foreground">Add a job description and choose <span className="text-foreground">Analyze match</span> to see real keyword coverage.</div>}
            </aside>

            {/* Center: resume preview */}
            <section aria-labelledby="resume-preview-heading" className="min-w-0 rounded-3xl border border-border bg-card/40 p-6">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 id="resume-preview-heading" className="text-sm font-normal text-muted-foreground">Preview</h2>
                {lastDocId && resumePreviewText && !editingText && (
                  <button
                    type="button"
                    onClick={startEditingText}
                    disabled={templateMutation.isPending}
                    className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:bg-card hover:text-foreground disabled:opacity-60"
                  >
                    <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                    Edit text
                  </button>
                )}
              </div>
              {lastAtsScore != null && (
                <div className="mt-1 text-xs text-muted-foreground">
                  Tailored ATS score: <span className="font-medium text-foreground">{lastAtsScore}</span>
                  {lastMissingKeywords.length > 0 &&
                    ` · missing: ${lastMissingKeywords.slice(0, 5).join(", ")}`}
                </div>
              )}
              {/* Without a stored document + review (PDF storage failed) nothing
                  can be fixed, so fall back to listing the agent's warnings. */}
              {!(lastDocId && lastReview) && lastWarnings.length > 0 && (
                <div className="mt-3 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning" role="alert">
                  <p className="font-medium">Warnings</p>
                  <ul className="mt-2 list-disc space-y-1 pl-5">
                    {lastWarnings.map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}
                  </ul>
                </div>
              )}
              {aiSummary && <p className="mt-2 text-sm text-muted-foreground">{aiSummary}</p>}

              {lastDocId && resumePreviewText && !editingText && (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span id="resume-template-label" className="text-xs text-muted-foreground">Template</span>
                  <div role="group" aria-labelledby="resume-template-label" className="flex flex-wrap gap-1 rounded-full border border-border bg-muted/40 p-1">
                    {RESUME_TEMPLATES.map((tpl) => {
                      const active = (lastTemplate ?? selectedTemplate) === tpl.id;
                      const pending = templateMutation.isPending && templateMutation.variables === tpl.id;
                      return (
                        <button
                          key={tpl.id}
                          type="button"
                          aria-pressed={active}
                          disabled={templateMutation.isPending}
                          onClick={() => {
                            if (!active) templateMutation.mutate(tpl.id);
                          }}
                          className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs transition-colors disabled:cursor-not-allowed ${
                            active
                              ? "bg-background font-medium text-foreground shadow-sm"
                              : "text-muted-foreground hover:text-foreground disabled:opacity-60"
                          }`}
                        >
                          {pending && <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />}
                          {tpl.name}
                        </button>
                      );
                    })}
                  </div>
                  <span className="sr-only" aria-live="polite">
                    {templateMutation.isPending ? "Re-rendering the resume in the new template…" : ""}
                  </span>
                </div>
              )}

              {editingText ? (
                <div className="mt-3 space-y-3">
                  <label htmlFor="resume-markdown-editor" className="text-xs font-medium text-foreground">
                    Resume text (markdown)
                  </label>
                  <textarea
                    id="resume-markdown-editor"
                    value={draftMarkdown}
                    onChange={(e) => setDraftMarkdown(e.target.value)}
                    maxLength={MAX_MARKDOWN_LENGTH}
                    spellCheck
                    disabled={editTextMutation.isPending}
                    aria-describedby="resume-markdown-help"
                    className="h-[32rem] w-full resize-y rounded-2xl border border-border bg-background/60 px-4 py-3 font-mono text-xs leading-relaxed focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60"
                  />
                  <p id="resume-markdown-help" className="text-xs text-muted-foreground">
                    Keep the structure: <code># Name</code>, a contact line, <code>## SECTION</code> headings,{" "}
                    <code>### Role | Employer | Location | Mon YYYY - Present</code> and <code>- bullets</code>.{" "}
                    {draftMarkdown.length.toLocaleString()}/{MAX_MARKDOWN_LENGTH.toLocaleString()} characters.
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <LiquidGlassButton
                      tone="primary"
                      size="sm"
                      disabled={
                        editTextMutation.isPending ||
                        !draftMarkdown.trim() ||
                        draftMarkdown === resumePreviewText
                      }
                      onClick={() => editTextMutation.mutate(draftMarkdown)}
                    >
                      {editTextMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                      {editTextMutation.isPending ? "Saving…" : "Save changes"}
                    </LiquidGlassButton>
                    <LiquidGlassButton
                      tone="ghost"
                      size="sm"
                      disabled={editTextMutation.isPending}
                      onClick={cancelEditingText}
                    >
                      Cancel
                    </LiquidGlassButton>
                  </div>
                </div>
              ) : (
                <div
                  aria-busy={templateMutation.isPending}
                  className={`mt-3 max-h-[56rem] w-full overflow-auto rounded-2xl border border-border bg-muted/30 p-3 transition-opacity sm:p-4 ${
                    templateMutation.isPending ? "opacity-60" : ""
                  }`}
                >
                  {resumePreviewText ? (
                    <ResumePreview
                      markdown={resumePreviewText}
                      template={lastTemplate ?? selectedTemplate}
                      className="mx-auto"
                    />
                  ) : (
                    <div className="flex aspect-[8.5/11] w-full items-center justify-center p-8 text-center text-sm text-muted-foreground">Upload a resume, add a job description, then choose Tailor Resume to generate a real preview.</div>
                  )}
                </div>
              )}
            </section>

            {/* Right aside: AI suggestions */}
            <aside className="space-y-3">
              <div className="text-sm text-muted-foreground">Resume Agent changes</div>
              {aiChanges.length ? <div className="rounded-3xl border border-border bg-card/60 p-5"><ul className="list-disc space-y-2 pl-5 text-sm">{aiChanges.map((change, index) => <li key={`${index}-${change}`}>{change}</li>)}</ul><p className="mt-3 text-xs text-muted-foreground">These changes are reflected in the preview.</p></div> : <EmptyState title="No AI changes yet" description="Upload a resume and job description, then tailor it to see what the Resume Agent changed." />}
              <div className="pt-3 text-sm text-muted-foreground">ATS recommendations</div>
              {activeJobAts ? <SuggestionsList suggestions={insightData.suggestions} /> : <EmptyState title="No job analysis yet" description="Choose Analyze match to get keyword gaps and ATS recommendations for this job." />}
            </aside>
          </motion.div>

          {/* Fix missing details — own full-width row so the form has room;
              hidden while the raw text editor is open to avoid conflicting edits. */}
          {lastDocId && lastReview && !editingText && (
            <motion.div variants={fadeUp}>
              <ResumeFixPanel
                documentId={lastDocId}
                review={lastReview}
                contactSuggestions={contactSuggestions}
                warnings={lastWarnings}
                onFixed={applyTailored}
              />
            </motion.div>
          )}
        </>
      )}

    </motion.div>
  );
}
