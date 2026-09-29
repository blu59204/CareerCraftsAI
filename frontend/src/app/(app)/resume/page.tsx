"use client";

import { useState, useRef, useEffect, useCallback, type ReactNode } from "react";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import {
  UploadSimple,
  DownloadSimple,
  Target,
  FileText,
  MagicWand,
  CloudArrowUp,
  CircleNotch,
  PencilSimple,
  FolderOpen,
  Minus,
  Plus,
  Check,
  Copy,
  CaretDown,
  Palette,
  ClockCounterClockwise,
  EnvelopeSimple,
  Crosshair,
  Lightbulb,
  Sparkle,
  FilePdf,
  Warning,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import { useQuery, useMutation, useQueryClient, useIsMutating } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import {
  Bezel,
  Eyebrow,
  EmptyPanel,
  Hairline,
  IconButton,
  IslandButton,
  Notice,
  PanelTitle,
  Reveal,
  Screen,
  SectionHeading,
  Segmented,
  Skeleton,
  StatusPill,
  Textarea,
  Chip,
  EASE_OUT_EXPO,
  EASE_VANGUARD,
  listItem,
  listStagger,
  panelSwap,
  type StatusTone,
} from "@/components/vanguard";
import { AtsScoreRing } from "@/components/resume/AtsScoreRing";
import { KeywordCoverage } from "@/components/resume/KeywordCoverage";
import { SuggestionsList } from "@/components/resume/SuggestionsList";
import { ResumePreview } from "@/components/resume/ResumePreview";
import { ResumeFixPanel } from "@/components/resume/ResumeFixPanel";
import { SAMPLE_RESUME_MARKDOWN } from "@/components/resume/sample-resume";
import { apiClient, getApiErrorMessage, UserFacingError } from "@/lib/api";
import { getResumeInsightData } from "@/lib/resume-insights";
import { takePendingJd } from "@/lib/job-handoff";
import { postResumeFix, RESUME_TAILORED_KEY } from "@/lib/resume-api";
import {
  countOpenIssues,
  type ContactFields,
  type ResumeOptimizeResponse,
  type ResumeReview,
  type ResumeTemplateId,
  type TailoredResume,
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

/** A tailored-document reply plus the document generation its request started on. */
type Tailored = { data: TailoredResume; generation: number };

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

type WorkspaceTab = "builder" | "templates" | "history" | "cover-letter";

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

const WORKSPACE_TABS: ReadonlyArray<{ value: WorkspaceTab; label: string; icon: ReactNode }> = [
  { value: "builder", label: "Builder", icon: <MagicWand size={14} weight="light" /> },
  { value: "templates", label: "Templates", icon: <Palette size={14} weight="light" /> },
  { value: "history", label: "History", icon: <ClockCounterClockwise size={14} weight="light" /> },
  { value: "cover-letter", label: "Cover letter", icon: <EnvelopeSimple size={14} weight="light" /> },
];

/** Scale for template-card thumbnails (816px letter page → ~245px wide). */
const TEMPLATE_THUMB_SCALE = 0.35;

/** Backend limit for a manual markdown edit. */
const MAX_MARKDOWN_LENGTH = 30_000;

/** Backend limit for a job description (OptimizeRequest.jd_text). */
const MAX_JD_LENGTH = 20_000;

/**
 * Client-side cap for the cover-letter job description. The cover-letter
 * endpoint sets no length limit of its own; this reuses the resume cap.
 */
const MAX_COVER_JD_LENGTH = MAX_JD_LENGTH;

/** Main preview: minimum paper width (px) before it scrolls, and zoom range. */
const PREVIEW_MIN_WIDTH = 560;
const ZOOM_MIN = 0.6;
const ZOOM_MAX = 1.5;
const ZOOM_STEP = 0.1;

function clampZoom(value: number): number {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(value * 10) / 10));
}

function isTemplateId(value: unknown): value is TemplateId {
  return value === "modern" || value === "classic" || value === "technical";
}

// ---------------------------------------------------------------------------
// Small presentational helpers
// ---------------------------------------------------------------------------

function Spinner({ size = 15 }: { size?: number }) {
  return <CircleNotch size={size} weight="light" aria-hidden="true" className="animate-spin motion-reduce:animate-none" />;
}

/** Round icon medallion used in panel headers. */
function Medallion({ children }: { children: ReactNode }) {
  return (
    <span
      aria-hidden="true"
      className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-foreground/[0.04] text-foreground/80 ring-1 ring-foreground/[0.06] dark:bg-white/[0.05] dark:ring-white/10"
    >
      {children}
    </span>
  );
}

/** Recessed tray for previews / empty surfaces inside a bezel core. */
const TRAY = "rounded-[1.25rem] bg-foreground/[0.03] ring-1 ring-foreground/[0.05] dark:bg-white/[0.02] dark:ring-white/[0.07]";

/**
 * Left-column editorial hero. Same entrance choreography as the kit's
 * PageHero, but sized for a 4/12 column so the working area can sit beside it.
 */
function RailHero({ actions, status }: { actions: ReactNode; status?: ReactNode }) {
  const reduce = useReducedMotion();
  const enter = (delay: number) =>
    reduce
      ? { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { duration: 0.2 } }
      : {
          initial: { opacity: 0, y: 28, filter: "blur(10px)" },
          animate: { opacity: 1, y: 0, filter: "blur(0px)" },
          transition: { duration: 0.9, ease: EASE_OUT_EXPO, delay },
        };

  return (
    <header className="pt-4 md:pt-10">
      <motion.div {...enter(0)}>
        <Eyebrow>Resume workspace</Eyebrow>
      </motion.div>
      <motion.h1
        {...enter(0.06)}
        className="mt-6 text-balance font-geist text-[2.75rem] font-semibold leading-[0.95] tracking-[-0.05em] text-foreground sm:text-6xl lg:text-[3.6rem] xl:text-7xl"
      >
        Resume,
        <span className="block text-muted-foreground/70">tailored to the job.</span>
      </motion.h1>
      <motion.p {...enter(0.12)} className="mt-6 max-w-[44ch] text-pretty text-[15px] leading-7 text-muted-foreground">
        Paste a target job, scan keywords, improve bullets, and export once your preview is ready.
      </motion.p>
      <motion.div {...enter(0.18)} className="mt-7 flex flex-wrap items-center gap-2.5">
        {actions}
      </motion.div>
      {status}
    </header>
  );
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
    <div className="space-y-6">
      <SectionHeading
        eyebrow="Cover letter"
        title="Write the letter that goes with it."
        description="Uses your uploaded resume as context. Pick a tone, paste the posting, then edit the draft freely."
      />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {/* Input panel */}
        <Bezel coreClassName="space-y-5 p-5 md:p-6">
          <PanelTitle
            icon={<FileText size={15} weight="light" />}
            title={<label htmlFor="cover-jd">Job description</label>}
            meta="Required"
          />
          <div className="space-y-2">
            <Textarea
              id="cover-jd"
              value={jd}
              onChange={(e) => setJd(e.target.value)}
              maxLength={MAX_COVER_JD_LENGTH}
              aria-label="Job description"
              aria-describedby="cover-jd-count"
              placeholder="Paste the job description here to get a tailored cover letter…"
              className="min-h-40 resize-none"
            />
            <p id="cover-jd-count" className="pr-1 text-right text-xs tabular-nums text-muted-foreground">
              {jd.length.toLocaleString()}/{MAX_COVER_JD_LENGTH.toLocaleString()} characters
            </p>
          </div>

          <div>
            <p id="cover-tone-label" className="mb-2.5 pl-1 text-[12px] font-medium text-muted-foreground">
              Tone
            </p>
            <div role="group" aria-labelledby="cover-tone-label" className="flex flex-wrap gap-2">
              {COVER_LETTER_TONES.map((t) => (
                <Chip key={t} active={tone === t} onClick={() => setTone(t)}>
                  {t}
                </Chip>
              ))}
            </div>
          </div>

          <Hairline />

          <IslandButton
            tone="primary"
            size="md"
            disabled={generating || !jd.trim()}
            onClick={onGenerate}
            icon={generating ? <Spinner /> : <MagicWand size={15} weight="light" />}
          >
            {generating ? "Generating…" : "Generate Cover Letter"}
          </IslandButton>
        </Bezel>

        {/* Output panel */}
        <Bezel coreClassName="flex flex-col p-5 md:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-geist text-[15px] font-semibold tracking-[-0.015em] text-foreground">
              {letter ? <label htmlFor="cover-letter-output">Cover letter</label> : "Cover letter"}
            </h3>
            {letter && (
              <div className="flex gap-2">
                <IslandButton tone="ghost" size="sm" onClick={copyToClipboard} icon={<Copy size={14} weight="light" />}>
                  Copy
                </IslandButton>
                <IslandButton tone="ghost" size="sm" onClick={downloadText} icon={<DownloadSimple size={14} weight="light" />}>
                  Download text
                </IslandButton>
              </div>
            )}
          </div>
          <div className="mt-4 flex-1" aria-live="polite" aria-busy={generating || undefined}>
            {generating ? (
              <div className={cn(TRAY, "space-y-3 p-5")}>
                <span className="sr-only">Generating cover letter…</span>
                {[100, 80, 90, 60, 70, 85].map((w, i) => (
                  <div key={i} className="shimmer h-3.5 rounded-full" style={{ width: `${w}%` }} />
                ))}
              </div>
            ) : letter ? (
              <Textarea
                id="cover-letter-output"
                value={letter}
                onChange={(e) => setLetter(e.target.value)}
                className="h-80 resize-none leading-7"
              />
            ) : (
              <div className={cn(TRAY, "grid h-full min-h-60 place-items-center")}>
                <EmptyPanel
                  compact
                  icon={<EnvelopeSimple size={22} weight="light" />}
                  title="Your cover letter will appear here"
                  description="Generate a draft, then refine the wording before you send it anywhere."
                />
              </div>
            )}
          </div>
        </Bezel>
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
  /** Another resume request is in flight. */
  busy: boolean;
  /** The user's tailored resume; thumbnails show it instead of the sample. */
  previewMarkdown: string | null;
  displayName: string;
  /** Selecting a card also re-renders the open tailored resume's PDF. */
  hasTailoredResume: boolean;
}

function TemplateSelector({
  selected,
  onSelect,
  onTailor,
  isTailoring,
  canTailor,
  busy,
  previewMarkdown,
  displayName,
  hasTailoredResume,
}: TemplateSelectorProps) {
  const ownResume = !!previewMarkdown;
  const selectedName = RESUME_TEMPLATES.find((t) => t.id === selected)?.name ?? selected;
  return (
    <div className="space-y-6">
      <SectionHeading
        eyebrow="Templates"
        title="Choose a template."
        description={
          ownResume
            ? "Each card shows your tailored resume in that theme. All templates are single-column and ATS-safe."
            : "Cards show a sample resume — tailor yours to see it in each theme. All templates are single-column and ATS-safe."
        }
      />

      <motion.ul initial="hidden" animate="show" variants={listStagger} className="space-y-4">
        {RESUME_TEMPLATES.map((tpl, index) => {
          const isSelected = selected === tpl.id;
          return (
            <motion.li key={tpl.id} variants={listItem}>
              <Bezel
                tone={isSelected ? "primary" : "default"}
                coreClassName="grid grid-cols-1 gap-5 p-4 sm:grid-cols-[17.5rem_minmax(0,1fr)] sm:gap-6"
              >
                {/* Thumbnail rendered with the same layout as the PDF template */}
                <div
                  aria-hidden="true"
                  className={cn(TRAY, "pointer-events-none flex h-64 w-full select-none justify-center overflow-hidden pt-3")}
                >
                  <ResumePreview
                    markdown={previewMarkdown || SAMPLE_RESUME_MARKDOWN}
                    displayName={ownResume ? displayName : undefined}
                    template={tpl.id}
                    scale={TEMPLATE_THUMB_SCALE}
                  />
                </div>

                <div className="flex min-w-0 flex-col py-1 sm:pr-2">
                  <div className="flex items-center gap-3">
                    <span className="font-geist-mono text-[11px] tabular-nums text-muted-foreground">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="text-[10px] font-medium uppercase tracking-[0.18em] text-primary">{tpl.badge}</span>
                  </div>
                  <h3 className="mt-3 font-geist text-2xl font-semibold tracking-[-0.03em] text-foreground">{tpl.name}</h3>
                  <p className="mt-2 max-w-[44ch] text-sm leading-6 text-muted-foreground">{tpl.description}</p>

                  <div className="mt-auto flex items-center gap-3 pt-6">
                    <IslandButton
                      tone={isSelected ? "ghost" : "primary"}
                      size="sm"
                      aria-disabled={(busy && !isSelected) || undefined}
                      className="aria-disabled:cursor-not-allowed aria-disabled:opacity-60"
                      icon={isSelected ? <Check size={14} weight="light" /> : undefined}
                      onClick={() => {
                        if (!busy && !isSelected) onSelect(tpl.id);
                      }}
                    >
                      {isSelected ? "Selected ✓" : hasTailoredResume ? "Use for my resume" : "Select"}
                    </IslandButton>
                  </div>
                </div>
              </Bezel>
            </motion.li>
          );
        })}
      </motion.ul>

      <Bezel tone="muted" size="md" coreClassName="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <span className="pl-1 text-xs text-muted-foreground">Uses the job description from the Builder tab</span>
        <IslandButton
          tone="primary"
          size="sm"
          onClick={onTailor}
          disabled={busy || !canTailor}
          icon={isTailoring ? <Spinner size={14} /> : <MagicWand size={14} weight="light" />}
        >
          {isTailoring ? "Tailoring…" : `Tailor with ${selectedName} template`}
        </IslandButton>
      </Bezel>
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
  /** Another resume request is in flight: opening is blocked. */
  busy: boolean;
}

const RUN_STATUS_TONE: Record<AgentRun["status"], StatusTone> = {
  pending: "neutral",
  running: "primary",
  completed: "success",
  failed: "danger",
  awaiting_approval: "warning",
};

function HistoryTab({ agentRuns, isLoading, onDownload, onOpen, openingId, busy }: HistoryTabProps) {
  const heading = (
    <SectionHeading
      eyebrow="History"
      title="Past tailoring runs."
      description="Reopen any tailored resume in the builder, or download its PDF again."
    />
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        {heading}
        <Bezel coreClassName="space-y-3 p-4" aria-busy="true">
          <p className="sr-only" role="status">
            Loading history…
          </p>
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-[1rem]" />
          ))}
        </Bezel>
      </div>
    );
  }

  if (!agentRuns || agentRuns.length === 0) {
    return (
      <div className="space-y-6">
        {heading}
        <Bezel tone="muted">
          <EmptyPanel
            icon={<ClockCounterClockwise size={22} weight="light" />}
            title="Resume history"
            description="Previous tailoring runs will appear here once you tailor your first resume."
          />
        </Bezel>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {heading}
      <Bezel coreClassName="px-2 py-2 md:px-3">
        <motion.ul initial="hidden" animate="show" variants={listStagger} className="divide-y divide-foreground/[0.06] dark:divide-white/[0.07]">
          {agentRuns.map((run) => {
            const docId = typeof run.output?.pdf_document_id === "string" ? run.output.pdf_document_id : null;
            const isOpening = docId !== null && openingId === docId;
            return (
              <motion.li
                key={run.id}
                variants={listItem}
                className="flex flex-wrap items-center justify-between gap-3 px-3 py-4"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <Medallion>
                    <FilePdf size={16} weight="light" />
                  </Medallion>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground">Resume Agent Run</p>
                    <p className="text-xs tabular-nums text-muted-foreground">
                      {new Date(run.started_at).toLocaleString(undefined, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <StatusPill tone={RUN_STATUS_TONE[run.status] ?? "neutral"} live={run.status === "running"} className="capitalize">
                    {run.status.replace("_", " ")}
                  </StatusPill>
                  {docId && (
                    <>
                      <IslandButton
                        tone="ghost"
                        size="sm"
                        onClick={() => {
                          if (!busy) onOpen(docId);
                        }}
                        // aria-disabled (not disabled) keeps the button focusable while another request runs.
                        aria-disabled={busy || undefined}
                        aria-label="Open this tailored resume in the builder"
                        className="aria-disabled:cursor-not-allowed aria-disabled:opacity-60"
                        icon={isOpening ? <Spinner size={14} /> : <FolderOpen size={14} weight="light" />}
                      >
                        {isOpening ? "Opening…" : "Open"}
                      </IslandButton>
                      <IslandButton
                        tone="ghost"
                        size="sm"
                        onClick={() => onDownload(docId)}
                        aria-label="Download this tailored resume as PDF"
                        icon={<DownloadSimple size={14} weight="light" />}
                      >
                        PDF
                      </IslandButton>
                    </>
                  )}
                </div>
              </motion.li>
            );
          })}
        </motion.ul>
      </Bezel>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ResumePage() {
  const queryClient = useQueryClient();
  const reduceMotion = useReducedMotion();

  // UI state
  const [tab, setTab] = useState<WorkspaceTab>("builder");
  const [jdText, setJdText] = useState("");
  const [jdPanelOpen, setJdPanelOpen] = useState(true);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);

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

  // Close the Save-to-Drive menu on outside click or Escape.
  useEffect(() => {
    if (!showExportMenu) return;
    const onPointerDown = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) setShowExportMenu(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowExportMenu(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [showExportMenu]);

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
  const [previewTemplate, setPreviewTemplate] = useState<TemplateId | null>(null);
  const [aiChanges, setAiChanges] = useState<string[]>([]);
  const [aiSummary, setAiSummary] = useState<string | null>(null);
  /** The name the PDF prints (profile full name); "" uses the markdown `# Name`. */
  const [displayName, setDisplayName] = useState("");
  const [previewZoom, setPreviewZoom] = useState(1);
  const [jobAts, setJobAts] = useState<{ documentId: string; jdText: string; data: JobAtsAnalysis } | null>(null);

  // Bumped whenever the current document is replaced wholesale (new optimize,
  // new upload, history open). A tailored request captures it when it starts
  // and its result is dropped if it changed, so a slow reply can't overwrite
  // newer state.
  const docGenRef = useRef(0);

  // Manual markdown edit of the tailored resume
  const [editingText, setEditingText] = useState(false);
  const [draftMarkdown, setDraftMarkdown] = useState("");
  const markdownEditorRef = useRef<HTMLTextAreaElement>(null);
  const editButtonRef = useRef<HTMLButtonElement>(null);
  const restoreEditFocusRef = useRef(false);

  // Opening the editor focuses it; saving or cancelling returns focus to "Edit text".
  useEffect(() => {
    if (editingText) markdownEditorRef.current?.focus();
  }, [editingText]);

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
      toast.error(getApiErrorMessage(err, "Could not analyze this resume and job description"));
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
  const applyTailored = useCallback((r: TailoredResume) => {
    setResumePreviewText(r.resume_markdown);
    setLastReview(r.review);
    setLastWarnings(r.warnings ?? []);
    setLastAtsScore(r.ats_score ?? null);
    setLastMissingKeywords(r.keywords_missing ?? []);
    setLastTemplate(isTemplateId(r.template) ? r.template : null);
    setContactSuggestions(r.contact_suggestions ?? {});
    // /fix may answer with a new version (the old one is pinned by a pending
    // approval), so always follow the id the server returns.
    setLastDocId(r.document_id);
    setAiChanges(r.changes_made ?? []);
    setAiSummary(r.summary ?? null);
    setDisplayName(r.display_name ?? "");
  }, []);

  /** Applies `r` only if no newer document replaced the one the request started on. */
  const applyIfCurrent = useCallback(
    (r: TailoredResume, generation: number): boolean => {
      if (generation !== docGenRef.current) return false;
      applyTailored(r);
      return true;
    },
    [applyTailored],
  );
  const getGeneration = useCallback(() => docGenRef.current, []);

  const templateMutation = useMutation<Tailored, unknown, TemplateId>({
    mutationKey: [...RESUME_TAILORED_KEY, "template"],
    mutationFn: async (template) => {
      if (!lastDocId) throw new UserFacingError("Tailor your resume first.");
      const generation = docGenRef.current;
      return { data: await postResumeFix(lastDocId, { template }), generation };
    },
    // The preview switches instantly (previewTemplate); this request only
    // re-renders the downloadable PDF in the new theme.
    onMutate: (template) => setPreviewTemplate(template),
    onSuccess: ({ data, generation }, template) => {
      if (!applyIfCurrent(data, generation)) return;
      setSelectedTemplate(template);
      toast.success(`PDF updated to the ${RESUME_TEMPLATES.find((t) => t.id === template)?.name ?? template} template`);
    },
    onError: (err) => toast.error(getApiErrorMessage(err, "Could not switch the template")),
    onSettled: () => setPreviewTemplate(null),
  });

  const editTextMutation = useMutation<Tailored, unknown, string>({
    mutationKey: [...RESUME_TAILORED_KEY, "edit-text"],
    mutationFn: async (markdown) => {
      if (!lastDocId) throw new UserFacingError("Tailor your resume first.");
      const generation = docGenRef.current;
      return { data: await postResumeFix(lastDocId, { resume_markdown: markdown }), generation };
    },
    onSuccess: ({ data, generation }) => {
      if (!applyIfCurrent(data, generation)) return;
      restoreEditFocusRef.current = true;
      setEditingText(false);
      toast.success("Resume updated");
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, "Could not save your changes"));
      markdownEditorRef.current?.focus();
    },
  });

  const openTailoredMutation = useMutation<Tailored, unknown, string>({
    mutationKey: [...RESUME_TAILORED_KEY, "open"],
    mutationFn: async (documentId) => {
      // Opening a document replaces the current one: older replies are stale.
      const generation = ++docGenRef.current;
      const { data } = await apiClient.get(`/resume/tailored/${documentId}`);
      return { data: data as TailoredResume, generation };
    },
    onSuccess: ({ data, generation }) => {
      if (generation !== docGenRef.current) return;
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
    restoreEditFocusRef.current = true;
    setEditingText(false);
  };

  // -------------------------------------------------------------------------
  // Mutation: optimize/tailor resume
  // -------------------------------------------------------------------------
  const optimizeMutation = useMutation<{ data: OptimizeResult; generation: number }, unknown, string>({
    mutationFn: async (jdInput: string) => {
      const jd = jdInput.trim();
      if (!jd) throw new UserFacingError("Paste the job description before tailoring your resume.");
      const generation = ++docGenRef.current;
      // This call runs the LLM synchronously server-side (no SSE/queue) and
      // routinely takes 30-60s+ — well past the client's default 30s timeout,
      // which would abort a request the backend was about to complete.
      const { data } = await apiClient.post("/resume/optimize", {
        jd_text: jd,
        template: selectedTemplate,
      }, { timeout: 120_000 });
      return { data: data as OptimizeResult, generation };
    },
    onSuccess: async ({ data, generation }) => {
      // Approve the finished run even when its result is stale below, so it
      // never lingers as "awaiting approval". A failed approval doesn't undo
      // the tailored resume, so it doesn't block applying it.
      if (data.resume_markdown && data.run_id) {
        await apiClient.post(`/agents/${data.run_id}/approve`, { approved: true }).catch(() => undefined);
      }
      queryClient.invalidateQueries({ queryKey: ["resume-docs"] });
      queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
      // A newer upload / history open replaced the document meanwhile.
      if (generation !== docGenRef.current) return;
      setResumePreviewText(data.resume_markdown || null);
      // A new run replaces the previous document; without a stored PDF there
      // is nothing to fix or download, so don't keep pointing at the old one.
      setLastDocId(data.pdf_document_id ?? null);
      setLastReview(data.review ?? null);
      setContactSuggestions(data.contact_suggestions ?? {});
      setLastTemplate(isTemplateId(data.template) ? data.template : selectedTemplate);
      setEditingText(false);
      setAiChanges(data.changes_made ?? []);
      setAiSummary(data.summary ?? null);
      setDisplayName(data.display_name ?? "");
      setLastAtsScore(data.ats_score ?? null);
      setLastMissingKeywords(data.keywords_missing ?? []);
      setLastWarnings(data.warnings ?? []);
      const openIssues = countOpenIssues(data.review);
      if (openIssues > 0) toast.warning(`Resume tailored — ${openIssues} detail(s) need your input below.`);
      else if (data.warnings?.length) toast.warning(data.warnings[0]);
      else toast.success(data.ats_score != null ? `Resume tailored! ATS score ${data.ats_score}.` : "Resume tailored.");
    },
    onError: (err: unknown) => {
      const status = (err as { response?: { status?: number } })?.response?.status;
      // Joins FastAPI 422 detail arrays; "" when the backend gave no reason.
      const message = getApiErrorMessage(err, "");
      if (message === "jd_text cannot be empty") {
        toast.error("Paste the full job description before tailoring your resume.");
      } else if (status === 500 || message === "Agent failed") {
        toast.error("We couldn’t tailor your resume. Please try again; if it keeps happening, contact support.");
      } else {
        toast.error(message || "We couldn’t tailor your resume. Please try again.");
      }
    },
  });

  /** Any request that replaces the tailored document is in flight. */
  const tailoredPending = useIsMutating({ mutationKey: RESUME_TAILORED_KEY }) > 0;
  const busy = tailoredPending || optimizeMutation.isPending;
  // Theme shown in the preview: the one being switched to (instant), else the
  // one the PDF was rendered with, else the one picked for the next tailor run.
  const shownTemplate = previewTemplate ?? lastTemplate ?? selectedTemplate;

  // Templates tab "Select": with a tailored resume open, also switch its PDF.
  const selectTemplate = (id: TemplateId) => {
    setSelectedTemplate(id);
    if (lastDocId && !busy && id !== (lastTemplate ?? selectedTemplate)) templateMutation.mutate(id);
  };

  // The "Edit text" button is disabled while a request is pending (the save
  // itself settles a render after the editor closes), so wait until it's usable.
  // Only take focus back if it was lost with the removed editor (it sits on
  // <body> or a detached node); if the user moved on meanwhile, leave it.
  useEffect(() => {
    if (editingText || busy || !restoreEditFocusRef.current) return;
    restoreEditFocusRef.current = false;
    const active = document.activeElement;
    if (active && active !== document.body && active.isConnected) return;
    editButtonRef.current?.focus();
  }, [editingText, busy]);

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
      toast.error(getApiErrorMessage(err, "Could not save to Drive — connect Google in Settings"));
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
      // A new resume replaces the current document: in-flight replies are stale.
      docGenRef.current += 1;
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
      setDisplayName("");
      setJobAts(null);
      toast.success(`Resume uploaded: ${file.name}`);
      if ((data as { warning?: string }).warning) {
        toast.warning((data as { warning: string }).warning);
      }
      queryClient.invalidateQueries({ queryKey: ["resume-docs"] });
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Upload failed — try a PDF or DOCX file"));
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
  // Render helpers
  // -------------------------------------------------------------------------
  const panelVariants = reduceMotion
    ? { hidden: { opacity: 0 }, show: { opacity: 1, transition: { duration: 0.2 } }, exit: { opacity: 0, transition: { duration: 0.15 } } }
    : panelSwap;
  const scoreComputing = !!primaryDoc && primaryDoc.ats_score === null && !activeJobAts;
  const canShowTemplateBar = !!(lastDocId && resumePreviewText && !editingText);

  const heroActions = (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.doc,.docx"
        aria-label="Resume file (PDF or DOCX)"
        className="hidden"
        onChange={handleFileChange}
      />
      <IslandButton
        tone={primaryDoc ? "ghost" : "primary"}
        size="sm"
        disabled={uploading}
        onClick={() => fileInputRef.current?.click()}
        icon={uploading ? <Spinner size={14} /> : <UploadSimple size={14} weight="light" />}
      >
        {uploading ? "Uploading…" : "Upload"}
      </IslandButton>

      <div ref={exportMenuRef} className="relative">
        <IslandButton
          tone="ghost"
          size="sm"
          aria-haspopup="menu"
          aria-expanded={showExportMenu}
          aria-controls="resume-export-menu"
          onClick={() => setShowExportMenu((v) => !v)}
          icon={<CloudArrowUp size={14} weight="light" />}
          trailing={
            <CaretDown
              size={12}
              weight="light"
              className={cn("transition-transform duration-500 ease-vanguard", showExportMenu && "rotate-180")}
            />
          }
        >
          Save to Drive
        </IslandButton>
        <AnimatePresence>
          {showExportMenu && (
            <motion.div
              id="resume-export-menu"
              role="menu"
              aria-label="Save or download"
              initial={{ opacity: 0, y: -6, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -6, scale: 0.97 }}
              transition={{ duration: 0.3, ease: EASE_VANGUARD }}
              className="absolute left-0 top-full z-20 mt-2 w-60 origin-top-left rounded-[1.25rem] bg-foreground/[0.03] p-1 shadow-ambient ring-1 ring-foreground/[0.08] dark:bg-white/[0.04] dark:ring-white/10"
            >
              <div className="rounded-[calc(1.25rem-0.25rem)] bg-card p-1 shadow-bezel-core dark:shadow-bezel-core-dark">
                <button
                  type="button"
                  role="menuitem"
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
                  className="flex w-full items-center gap-2.5 rounded-[0.85rem] px-3 py-2.5 text-left text-sm text-foreground transition-colors duration-300 ease-vanguard hover:bg-foreground/[0.05] focus-visible:bg-foreground/[0.05] focus-visible:outline-none disabled:opacity-60 dark:hover:bg-white/[0.06]"
                >
                  {saveToDriveMutation.isPending ? (
                    <Spinner size={15} />
                  ) : (
                    <CloudArrowUp size={15} weight="light" className="text-muted-foreground" aria-hidden="true" />
                  )}
                  {saveToDriveMutation.isPending ? "Saving…" : "Save to Google Drive"}
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setShowExportMenu(false);
                    handleDownloadPdf();
                  }}
                  className="flex w-full items-center gap-2.5 rounded-[0.85rem] px-3 py-2.5 text-left text-sm text-foreground transition-colors duration-300 ease-vanguard hover:bg-foreground/[0.05] focus-visible:bg-foreground/[0.05] focus-visible:outline-none dark:hover:bg-white/[0.06]"
                >
                  <DownloadSimple size={15} weight="light" className="text-muted-foreground" aria-hidden="true" /> Download PDF
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <IslandButton
        tone={lastDocId ? "primary" : "ghost"}
        size="sm"
        onClick={() => handleDownloadPdf()}
        disabled={!lastDocId}
        title={lastDocId ? "Download tailored PDF" : "Tailor your resume first to generate a PDF"}
        icon={<DownloadSimple size={14} weight="light" />}
      >
        Export
      </IslandButton>
    </>
  );

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  return (
    <Screen>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:grid-rows-[auto_auto_1fr] lg:gap-x-10 lg:gap-y-6">
        {/* ── Left column, row 1: editorial type block ─────────────────── */}
        <div className="min-w-0 lg:col-span-5 lg:col-start-1 lg:row-start-1 xl:col-span-4">
          <RailHero
            actions={heroActions}
            status={
              <p className="sr-only" aria-live="polite">
                {uploading ? "Uploading resume…" : ""}
              </p>
            }
          />
        </div>

        {/* ── Left column, row 2: primary resume + ATS ring ────────────── */}
        <Reveal className="min-w-0 lg:col-span-5 lg:col-start-1 lg:row-start-2 xl:col-span-4" delay={0.1}>
          <section aria-labelledby="primary-resume-heading">
            <Bezel lifted coreClassName="p-5 md:p-6">
              <div className="flex items-center justify-between gap-3">
                <h2 id="primary-resume-heading" className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Primary resume
                </h2>
                {primaryDoc && !docsLoading ? (
                  scoreComputing ? (
                    <StatusPill tone="primary" live>Scoring</StatusPill>
                  ) : activeJobAts ? (
                    <StatusPill tone="success">Analyzed</StatusPill>
                  ) : (
                    <StatusPill tone="neutral">Baseline</StatusPill>
                  )
                ) : null}
              </div>

              <div className="mt-5" aria-live="polite">
                {docsLoading ? (
                  <div className="flex items-center gap-5">
                    <Skeleton className="h-32 w-32 shrink-0 rounded-full" />
                    <div className="flex-1 space-y-3">
                      <Skeleton className="h-4 w-3/4 rounded-full" />
                      <Skeleton className="h-3 w-1/2 rounded-full" />
                      <p className="text-xs text-muted-foreground">Loading resume…</p>
                    </div>
                  </div>
                ) : primaryDoc ? (
                  <div className="flex flex-col items-start gap-5 sm:flex-row sm:items-center">
                    {insightData.score != null ? (
                      <AtsScoreRing score={insightData.score} size={136} />
                    ) : (
                      <div className="grid h-[136px] w-[136px] shrink-0 place-items-center rounded-full ring-1 ring-foreground/[0.07] dark:ring-white/10">
                        <span className="flex flex-col items-center gap-2 text-center text-[11px] text-muted-foreground">
                          <Spinner size={18} />
                          Calculating
                        </span>
                      </div>
                    )}
                    <div className="min-w-0 flex-1 space-y-3">
                      <div className="flex min-w-0 items-center gap-2">
                        <FilePdf size={16} weight="light" aria-hidden="true" className="shrink-0 text-muted-foreground" />
                        <span className="truncate font-geist-mono text-xs text-foreground" title={primaryDoc.filename}>
                          {primaryDoc.filename}
                        </span>
                      </div>
                      <Hairline />
                      {insightData.score != null ? (
                        <p className="text-xs leading-5 text-muted-foreground">
                          <span className="font-medium text-foreground">{insightData.scoreLabel}</span>
                          {activeJobAts ? " for this job" : " · run Analyze match for job-specific results"}
                        </p>
                      ) : (
                        <p className="text-xs leading-5 text-muted-foreground">Calculating your baseline ATS score…</p>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className={TRAY}>
                    <EmptyPanel
                      compact
                      icon={<UploadSimple size={22} weight="light" />}
                      title="No resume yet"
                      description="Upload a resume (PDF or DOCX) to see your ATS score. It also becomes the context every agent works from."
                      action={
                        <IslandButton
                          tone="ghost"
                          size="sm"
                          disabled={uploading}
                          onClick={() => fileInputRef.current?.click()}
                          icon={<FolderOpen size={14} weight="light" />}
                        >
                          Choose file
                        </IslandButton>
                      }
                    />
                  </div>
                )}
                {docsError && (
                  <Notice tone="danger" icon={<Warning size={16} weight="light" />} className="mt-4 text-xs">
                    Could not load your resume.
                  </Notice>
                )}
              </div>
            </Bezel>
          </section>
        </Reveal>

        {/* ── Right column: the working area ───────────────────────────── */}
        <div className="min-w-0 space-y-6 lg:col-span-7 lg:col-start-6 lg:row-span-3 lg:row-start-1 lg:pt-10 xl:col-span-8 xl:col-start-5">
          <Reveal subtle className="flex flex-wrap items-center justify-between gap-3">
            <Segmented<WorkspaceTab>
              value={tab}
              onChange={setTab}
              options={WORKSPACE_TABS}
              ariaLabel="Resume workspace sections"
            />
            <div aria-live="polite" className="flex items-center gap-2">
              {optimizeMutation.isPending ? (
                <StatusPill tone="primary" live>Resume Agent is tailoring</StatusPill>
              ) : lastDocId ? (
                <StatusPill tone="success">Tailored PDF ready</StatusPill>
              ) : null}
            </div>
          </Reveal>

          <AnimatePresence mode="wait">
            <motion.div
              key={tab}
              role="tabpanel"
              aria-label={WORKSPACE_TABS.find((t) => t.value === tab)?.label}
              variants={panelVariants}
              initial="hidden"
              animate="show"
              exit="exit"
              className="space-y-6"
            >
              {tab === "templates" && (
                <TemplateSelector
                  selected={shownTemplate}
                  onSelect={selectTemplate}
                  onTailor={() => optimizeMutation.mutate(jdText)}
                  isTailoring={optimizeMutation.isPending}
                  canTailor={!!primaryDoc && !!jdText.trim()}
                  busy={busy}
                  previewMarkdown={resumePreviewText}
                  displayName={displayName}
                  hasTailoredResume={!!lastDocId}
                />
              )}

              {tab === "history" && (
                <HistoryTab
                  agentRuns={agentRuns}
                  isLoading={runsLoading}
                  onDownload={handleDownloadPdf}
                  onOpen={(id) => {
                    if (!busy) openTailoredMutation.mutate(id);
                  }}
                  openingId={openTailoredMutation.isPending ? (openTailoredMutation.variables ?? null) : null}
                  busy={busy}
                />
              )}

              {tab === "cover-letter" && (
                <CoverLetterGenerator
                  tone={coverTone}
                  setTone={setCoverTone}
                  jd={coverJd}
                  setJd={setCoverJd}
                  letter={coverLetter}
                  setLetter={setCoverLetter}
                  generating={generating}
                  onGenerate={generateCoverLetter}
                />
              )}

              {tab === "builder" && (
                <>
                  {/* JD composer */}
                  <section aria-labelledby="resume-jd-heading">
                    <Bezel tone="primary" coreClassName="p-5 md:p-6">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex min-w-0 items-center gap-3">
                          <Medallion>
                            <Target size={16} weight="light" />
                          </Medallion>
                          <div className="min-w-0">
                            <h2 id="resume-jd-heading" className="font-geist text-[15px] font-semibold tracking-[-0.015em] text-foreground">
                              Target Job Description
                            </h2>
                            <p className="text-xs text-muted-foreground">The posting you want this resume to win.</p>
                          </div>
                          {jdText && <StatusPill tone="primary">Active</StatusPill>}
                        </div>
                        <IslandButton
                          tone="quiet"
                          size="sm"
                          aria-expanded={jdPanelOpen}
                          aria-controls="resume-jd-body"
                          onClick={() => setJdPanelOpen(!jdPanelOpen)}
                        >
                          {jdPanelOpen ? "Hide" : "Show JD"}
                        </IslandButton>
                      </div>

                      <div id="resume-jd-body">
                        {jdPanelOpen ? (
                          <div className="mt-5 space-y-3">
                            <Textarea
                              value={jdText}
                              onChange={(e) => setJdText(e.target.value)}
                              maxLength={MAX_JD_LENGTH}
                              aria-label="Target job description"
                              aria-describedby="resume-jd-count"
                              placeholder="Paste the job description here… CareerCraft AI will analyze requirements, match keywords, and suggest targeted resume bullets."
                              className="min-h-36 resize-y"
                            />

                            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                              <p id="resume-jd-count" className="pl-1 text-xs tabular-nums text-muted-foreground">
                                {jdText.length.toLocaleString()}/{MAX_JD_LENGTH.toLocaleString()} characters
                              </p>
                              <div className="flex flex-wrap gap-2">
                                <IslandButton
                                  tone="ghost"
                                  size="sm"
                                  disabled={!primaryDoc || atsMutation.isPending || !jdText.trim()}
                                  onClick={() => primaryDoc && atsMutation.mutate({ documentId: primaryDoc.id, jdText: jdText.trim() })}
                                  icon={atsMutation.isPending ? <Spinner size={14} /> : <Crosshair size={14} weight="light" />}
                                >
                                  {atsMutation.isPending ? "Analyzing…" : "Analyze match"}
                                </IslandButton>
                                <IslandButton
                                  tone="primary"
                                  size="sm"
                                  disabled={!primaryDoc || busy || !jdText.trim()}
                                  onClick={() => optimizeMutation.mutate(jdText)}
                                  trailing={optimizeMutation.isPending ? <Spinner size={14} /> : <MagicWand size={14} weight="light" />}
                                >
                                  {optimizeMutation.isPending ? "Tailoring…" : "Tailor Resume ✨"}
                                </IslandButton>
                              </div>
                            </div>

                            {docsError && (
                              <Notice tone="danger" icon={<Warning size={16} weight="light" />}>
                                Could not load your resumes. Refresh the page and try again.
                              </Notice>
                            )}
                            {!primaryDoc && !docsLoading && (
                              <p className="pl-1 text-sm text-muted-foreground">Upload a resume before analyzing or tailoring it.</p>
                            )}

                            <Hairline className="!mt-5" />
                            <ul className="flex flex-wrap items-center gap-x-5 gap-y-2 pl-1 text-xs text-muted-foreground">
                              {["Keyword matching", "Bullet rewriting", "Skills gap analysis"].map((cap) => (
                                <li key={cap} className="inline-flex items-center gap-1.5">
                                  <Check size={12} weight="light" aria-hidden="true" className="text-primary" />
                                  {cap}
                                </li>
                              ))}
                            </ul>
                          </div>
                        ) : (
                          <p className="mt-3 pl-1 text-xs tabular-nums text-muted-foreground">
                            {jdText.trim()
                              ? `Job description hidden · ${jdText.length.toLocaleString()} characters`
                              : "Job description hidden"}
                          </p>
                        )}
                      </div>
                    </Bezel>
                  </section>

                  {/* Preview */}
                  <section aria-labelledby="resume-preview-heading">
                    <Bezel coreClassName="p-4 md:p-6">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0 pl-1">
                          <h2 id="resume-preview-heading" className="font-geist text-[15px] font-semibold tracking-[-0.015em] text-foreground">
                            Preview
                          </h2>
                          {lastAtsScore != null ? (
                            <p className="mt-1 text-xs text-muted-foreground">
                              Tailored ATS score: <span className="font-medium tabular-nums text-foreground">{lastAtsScore}</span>
                              {lastMissingKeywords.length > 0 &&
                                ` · missing: ${lastMissingKeywords.slice(0, 5).join(", ")}`}
                            </p>
                          ) : (
                            <p className="mt-1 text-xs text-muted-foreground">
                              {resumePreviewText ? "Rendered with the PDF template." : "Your tailored resume renders here."}
                            </p>
                          )}
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          {lastDocId && resumePreviewText && !editingText && (
                            <IslandButton
                              ref={editButtonRef}
                              tone="ghost"
                              size="sm"
                              onClick={startEditingText}
                              disabled={busy}
                              icon={<PencilSimple size={14} weight="light" />}
                            >
                              Edit text
                            </IslandButton>
                          )}
                          {lastDocId && (
                            <IslandButton
                              tone="ghost"
                              size="sm"
                              onClick={() => handleDownloadPdf()}
                              icon={<DownloadSimple size={14} weight="light" />}
                            >
                              Download PDF
                            </IslandButton>
                          )}
                        </div>
                      </div>

                      {/* Without a stored document + review (PDF storage failed) nothing
                          can be fixed, so fall back to listing the agent's warnings. */}
                      {!(lastDocId && lastReview) && lastWarnings.length > 0 && (
                        <div className="mt-4 flex items-start gap-3 rounded-2xl bg-warning/10 px-4 py-3.5 text-sm leading-6 text-warning ring-1 ring-warning/25" role="alert">
                          <Warning size={16} weight="light" aria-hidden="true" className="mt-1 shrink-0" />
                          <div className="min-w-0">
                            <p className="font-medium">Warnings</p>
                            <ul className="mt-1.5 list-disc space-y-1 pl-5">
                              {lastWarnings.map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}
                            </ul>
                          </div>
                        </div>
                      )}
                      {aiSummary && <p className="mt-4 max-w-[70ch] pl-1 text-sm leading-6 text-muted-foreground">{aiSummary}</p>}

                      {aiChanges.length > 0 && (
                        <div className={cn(TRAY, "mt-4 p-4 md:p-5")}>
                          <div className="flex items-center gap-2">
                            <Sparkle size={14} weight="light" aria-hidden="true" className="text-primary" />
                            <h3 className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">Resume Agent changes</h3>
                          </div>
                          <ul className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 text-sm leading-6 text-foreground/90 md:grid-cols-2">
                            {aiChanges.map((change, index) => (
                              <li key={`${index}-${change}`} className="flex gap-2.5">
                                <span aria-hidden="true" className="mt-[0.6rem] h-1 w-1 shrink-0 rounded-full bg-primary" />
                                <span className="min-w-0">{change}</span>
                              </li>
                            ))}
                          </ul>
                          <p className="mt-3 text-xs text-muted-foreground">These changes are reflected in the preview.</p>
                        </div>
                      )}

                      {(canShowTemplateBar || (resumePreviewText && !editingText)) && (
                        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                          {canShowTemplateBar ? (
                            <div className="flex flex-wrap items-center gap-2">
                              <span id="resume-template-label" className="pl-1 text-xs text-muted-foreground">Template</span>
                              <div
                                role="group"
                                aria-labelledby="resume-template-label"
                                className="inline-flex flex-wrap gap-1 rounded-full bg-foreground/[0.035] p-1 ring-1 ring-foreground/[0.06] dark:bg-white/[0.04] dark:ring-white/10"
                              >
                                {RESUME_TEMPLATES.map((tpl) => {
                                  const active = shownTemplate === tpl.id;
                                  const pending = templateMutation.isPending && templateMutation.variables === tpl.id;
                                  return (
                                    <button
                                      key={tpl.id}
                                      type="button"
                                      aria-pressed={active}
                                      // aria-disabled instead of disabled: the pill the user
                                      // just pressed keeps keyboard focus while re-rendering.
                                      aria-disabled={busy || undefined}
                                      onClick={() => {
                                        if (!busy && !active) templateMutation.mutate(tpl.id);
                                      }}
                                      className={cn(
                                        "inline-flex h-7 items-center gap-1.5 rounded-full px-3 text-xs font-medium transition-[background-color,color,box-shadow] duration-500 ease-vanguard",
                                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring aria-disabled:cursor-not-allowed",
                                        active
                                          ? "bg-card text-foreground shadow-bezel-core ring-1 ring-foreground/[0.06] dark:bg-white/10 dark:shadow-none dark:ring-white/10"
                                          : "text-muted-foreground hover:text-foreground aria-disabled:opacity-60",
                                      )}
                                    >
                                      {pending && <Spinner size={12} />}
                                      {tpl.name}
                                    </button>
                                  );
                                })}
                              </div>
                              <span className="text-xs text-muted-foreground" aria-live="polite">
                                {templateMutation.isPending
                                  ? "Preview updated · regenerating the PDF…"
                                  : "Click a theme to see your resume in it"}
                              </span>
                            </div>
                          ) : (
                            <span />
                          )}

                          {resumePreviewText && !editingText && (
                            <div className="flex items-center gap-1" role="group" aria-label="Preview zoom">
                              <IconButton
                                size="sm"
                                onClick={() => setPreviewZoom((z) => clampZoom(z - ZOOM_STEP))}
                                disabled={previewZoom <= ZOOM_MIN}
                                aria-label="Zoom out"
                              >
                                <Minus size={13} weight="light" aria-hidden="true" />
                              </IconButton>
                              <button
                                type="button"
                                onClick={() => setPreviewZoom(1)}
                                aria-label={`Zoom ${Math.round(previewZoom * 100)}%, reset to 100%`}
                                className="h-7 min-w-[3.5rem] rounded-full px-2 font-geist-mono text-[11px] tabular-nums text-muted-foreground ring-1 ring-foreground/[0.06] transition-colors duration-500 ease-vanguard hover:bg-foreground/[0.05] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:ring-white/10 dark:hover:bg-white/[0.06]"
                              >
                                {Math.round(previewZoom * 100)}%
                              </button>
                              <IconButton
                                size="sm"
                                onClick={() => setPreviewZoom((z) => clampZoom(z + ZOOM_STEP))}
                                disabled={previewZoom >= ZOOM_MAX}
                                aria-label="Zoom in"
                              >
                                <Plus size={13} weight="light" aria-hidden="true" />
                              </IconButton>
                            </div>
                          )}
                        </div>
                      )}

                      {editingText ? (
                        <div className="mt-4 space-y-3">
                          <label htmlFor="resume-markdown-editor" className="block pl-1 text-[12px] font-medium text-muted-foreground">
                            Resume text (markdown)
                          </label>
                          <Textarea
                            ref={markdownEditorRef}
                            id="resume-markdown-editor"
                            value={draftMarkdown}
                            onChange={(e) => setDraftMarkdown(e.target.value)}
                            maxLength={MAX_MARKDOWN_LENGTH}
                            spellCheck
                            // readOnly (not disabled) while saving so keyboard focus stays put.
                            readOnly={editTextMutation.isPending}
                            aria-busy={editTextMutation.isPending || undefined}
                            aria-describedby="resume-markdown-help"
                            className="h-[32rem] font-geist-mono text-xs leading-relaxed read-only:opacity-60"
                          />
                          <p id="resume-markdown-help" className="pl-1 text-xs leading-5 text-muted-foreground">
                            Keep the structure: <code className="font-geist-mono">{"# Name"}</code>, a contact line,{" "}
                            <code className="font-geist-mono">{"## SECTION"}</code> headings,{" "}
                            <code className="font-geist-mono">{"### Role | Employer | Location | Mon YYYY - Present"}</code> (leave a missing part empty, e.g.{" "}
                            <code className="font-geist-mono">{"### Role |  | Remote | 2021 - 2022"}</code>) and{" "}
                            <code className="font-geist-mono">{"- bullets"}</code>.{" "}
                            <span className="tabular-nums">
                              {draftMarkdown.length.toLocaleString()}/{MAX_MARKDOWN_LENGTH.toLocaleString()}
                            </span>{" "}
                            characters.
                          </p>
                          <div className="flex flex-wrap items-center gap-2">
                            <IslandButton
                              tone="primary"
                              size="sm"
                              disabled={
                                busy ||
                                !draftMarkdown.trim() ||
                                draftMarkdown === resumePreviewText
                              }
                              onClick={() => editTextMutation.mutate(draftMarkdown)}
                              icon={editTextMutation.isPending ? <Spinner size={14} /> : undefined}
                            >
                              {editTextMutation.isPending ? "Saving…" : "Save changes"}
                            </IslandButton>
                            <IslandButton
                              tone="ghost"
                              size="sm"
                              disabled={editTextMutation.isPending}
                              onClick={cancelEditingText}
                            >
                              Cancel
                            </IslandButton>
                          </div>
                        </div>
                      ) : (
                        <div
                          aria-busy={busy}
                          className={cn(
                            TRAY,
                            "mt-4 max-h-[56rem] w-full overflow-auto p-3 transition-opacity duration-500 ease-vanguard sm:p-4",
                            tailoredPending && !templateMutation.isPending && "opacity-60",
                          )}
                        >
                          {resumePreviewText ? (
                            <ResumePreview
                              markdown={resumePreviewText}
                              template={shownTemplate}
                              displayName={displayName}
                              zoom={previewZoom}
                              minWidth={PREVIEW_MIN_WIDTH}
                              showPageBreaks
                              className="mx-auto"
                            />
                          ) : (
                            <div className="grid min-h-[22rem] place-items-center">
                              <EmptyPanel
                                compact
                                icon={optimizeMutation.isPending ? <Spinner size={22} /> : <FileText size={22} weight="light" />}
                                title={optimizeMutation.isPending ? "Tailoring your resume…" : "No preview yet"}
                                description={
                                  optimizeMutation.isPending
                                    ? "The Resume Agent is rewriting against this job. This usually takes 30–60 seconds."
                                    : "Upload a resume, add a job description, then choose Tailor Resume to generate a real preview."
                                }
                              />
                            </div>
                          )}
                        </div>
                      )}
                    </Bezel>
                  </section>

                  {/* Fix missing details — own full-width row so the form has room;
                      hidden while the raw text editor is open to avoid conflicting edits. */}
                  {lastDocId && lastReview && !editingText && (
                    <ResumeFixPanel
                      documentId={lastDocId}
                      review={lastReview}
                      contactSuggestions={contactSuggestions}
                      warnings={lastWarnings}
                      onFixed={applyIfCurrent}
                      getGeneration={getGeneration}
                      disabled={busy}
                    />
                  )}
                </>
              )}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* ── Left column, row 3: job analysis (keywords + recommendations) ── */}
        <Reveal className="min-w-0 space-y-6 lg:col-span-5 lg:col-start-1 lg:row-start-3 lg:self-start xl:col-span-4" delay={0.16}>
          {activeJobAts ? (
            <>
              <KeywordCoverage matched={insightData.matched} missing={insightData.missing} />
              <Bezel coreClassName="p-5 md:p-6">
                <PanelTitle
                  icon={<Lightbulb size={15} weight="light" />}
                  title="ATS recommendations"
                  meta={<span className="tabular-nums">{insightData.suggestions.length}</span>}
                />
                <div className="mt-5">
                  {insightData.suggestions.length ? (
                    <SuggestionsList suggestions={insightData.suggestions} />
                  ) : (
                    <p className="text-sm text-muted-foreground">No recommendations for this job.</p>
                  )}
                </div>
              </Bezel>
            </>
          ) : (
            <Bezel tone="muted">
              <EmptyPanel
                compact
                icon={<Crosshair size={22} weight="light" />}
                title="No job analysis yet"
                description={
                  <>
                    Add a job description and choose <span className="text-foreground">Analyze match</span> to see real keyword coverage and ATS recommendations.
                  </>
                }
              />
            </Bezel>
          )}
        </Reveal>
      </div>
    </Screen>
  );
}
