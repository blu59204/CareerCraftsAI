"use client";

import {
  memo,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type FormEvent,
  type HTMLAttributes,
  type ReactNode,
  type RefObject,
} from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2, ChevronDown, Info, Loader2, Plus, Trash2 } from "lucide-react";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { getApiErrorMessage } from "@/lib/api";
import { postResumeFix, RESUME_TAILORED_KEY } from "@/lib/resume-api";
import { cn } from "@/lib/utils";
import {
  countOpenIssues,
  type ContactFieldKey,
  type ContactFields,
  type EducationFix,
  type ExperienceFix,
  type ResumeFixPayload,
  type ResumeReview,
  type ReviewEntry,
  type ReviewIssue,
  type TailoredResume,
} from "@/lib/resume-types";

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export interface ResumeFixPanelProps {
  documentId: string;
  review: ResumeReview;
  contactSuggestions: Partial<ContactFields>;
  warnings: string[];
  /**
   * Applies a fix result. `generation` is the value `getGeneration()` returned
   * when the request started; returns false when the result was stale and ignored.
   */
  onFixed: (r: TailoredResume, generation: number) => boolean;
  /** Current document generation (bumped by a new optimize / upload / history open). */
  getGeneration: () => number;
  /** Another resume request is in flight: submitting is blocked. */
  disabled?: boolean;
}

/**
 * Form that lets the user fill the gaps the Resume Agent found (contact line,
 * employer names, dates, education) and re-render the tailored PDF.
 *
 * Form state is reset whenever a new review arrives (e.g. after a successful
 * fix) by keying the inner form on the document id + review contents. The
 * wrapper outlives those remounts, so it moves focus to the new form's
 * heading after a fix (the "Resume updated" toast is the announcement).
 */
function ResumeFixPanelImpl(props: ResumeFixPanelProps) {
  const formKey = `${props.documentId}:${JSON.stringify(props.review ?? null)}:${JSON.stringify(props.contactSuggestions ?? {})}`;
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [fixCount, setFixCount] = useState(0);
  const onApplied = useCallback(() => setFixCount((n) => n + 1), []);

  // Runs after the commit that remounted the form, so the ref points at the
  // new heading.
  useEffect(() => {
    if (fixCount > 0) headingRef.current?.focus();
  }, [fixCount]);

  return <ResumeFixForm key={formKey} {...props} headingRef={headingRef} onApplied={onApplied} />;
}

export const ResumeFixPanel = memo(ResumeFixPanelImpl);

// ---------------------------------------------------------------------------
// Styling
// ---------------------------------------------------------------------------

const INPUT =
  "w-full rounded-xl border border-border bg-background/60 px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-60";
const INPUT_WARNING = "border-warning/60 bg-warning/10";
const INPUT_ERROR = "border-danger/60";
const LABEL = "text-xs font-medium text-foreground";
const CHECKBOX = "h-4 w-4 shrink-0 rounded border-border accent-primary";
const SUB_CARD = "rounded-2xl border border-border bg-background/40 p-4";

// ---------------------------------------------------------------------------
// Dates: <input type="month"> "YYYY-MM"  <->  resume "Mon YYYY"
// ---------------------------------------------------------------------------

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] as const;
const MONTH_NAMES = [
  "january", "february", "march", "april", "may", "june",
  "july", "august", "september", "october", "november", "december",
] as const;
const PRESENT_RE = /^(present|current|now|ongoing)$/i;
const YEAR_RE = /\b(?:19|20)\d{2}\b/;
const DATE_FORMAT_HINT = "Use a format like Jun 2025";

/** "2025-06" -> "Jun 2025"; "" for anything else. */
function monthInputToLabel(value: string): string {
  const m = /^(\d{4})-(\d{1,2})$/.exec(value.trim());
  if (!m) return "";
  const month = Number(m[2]);
  if (month < 1 || month > 12) return "";
  return `${MONTHS[month - 1]} ${m[1]}`;
}

function toMonthInput(year: string, month: number): string | null {
  if (month < 1 || month > 12) return null;
  return `${year}-${String(month).padStart(2, "0")}`;
}

/**
 * "Jun 2025" / "June 2025" / "Sept. 2025" / "2025-6" / "2025-06" / "06/2025"
 * -> "2025-06"; null when the value isn't month-precise.
 */
function labelToMonthInput(label: string): string | null {
  const s = label.trim().replace(/\s+/g, " ");
  const named = /^([A-Za-z]{3,9})\.?,? (\d{4})$/.exec(s);
  if (named) {
    const word = named[1].toLowerCase();
    const idx = MONTH_NAMES.findIndex((name) => name.startsWith(word));
    return idx >= 0 ? toMonthInput(named[2], idx + 1) : null;
  }
  const iso = /^(\d{4})-(\d{1,2})$/.exec(s);
  if (iso) return toMonthInput(iso[1], Number(iso[2]));
  const slash = /^(\d{1,2})\/(\d{4})$/.exec(s);
  if (slash) return toMonthInput(slash[2], Number(slash[1]));
  return null;
}

/**
 * The label a date field sends: month-precise values are normalised to
 * "Mon YYYY"; anything else (a year, "Spring 2023", half-typed text) is kept
 * exactly as typed — a non-empty value is never turned into "".
 */
function normalizeDateLabel(raw: string): string {
  const text = (raw ?? "").trim().replace(/\s+/g, " ");
  if (!text) return "";
  const month = labelToMonthInput(text);
  return month ? monthInputToLabel(month) : text;
}

/** Soft check for typed dates: month-precise, a year, or Present-style. */
function looksLikeDate(raw: string): boolean {
  const text = raw.trim();
  return !text || !!labelToMonthInput(text) || YEAR_RE.test(text) || PRESENT_RE.test(text);
}

/** Browsers without a native month control (Firefox, desktop Safari) render type=month as text. */
let monthInputSupport: boolean | null = null;
function detectMonthInput(): boolean {
  if (monthInputSupport === null) {
    const input = document.createElement("input");
    input.setAttribute("type", "month");
    monthInputSupport = input.type === "month";
  }
  return monthInputSupport;
}
const subscribeNever = () => () => {};
/** false during SSR/hydration (text mode), then the real client capability. */
function useMonthInputSupported(): boolean {
  return useSyncExternalStore(subscribeNever, detectMonthInput, () => false);
}

/**
 * A date field. `text` is always the value as the user sees it ("Jun 2025",
 * "2023", "Spring 2023"); month mode shows it in a native month picker when
 * the text is month-precise.
 */
interface DateValue {
  mode: "month" | "text";
  text: string;
}

function dateFromLabel(raw: string): DateValue {
  const text = (raw ?? "").trim();
  return { mode: !text || labelToMonthInput(text) ? "month" : "text", text };
}

function dateToLabel(value: DateValue): string {
  return normalizeDateLabel(value.text);
}

function dateOrder(label: string): { year: number; month: number | null } | null {
  const month = labelToMonthInput(label);
  if (month) {
    const [y, m] = month.split("-").map(Number);
    return { year: y, month: m };
  }
  const year = /\b(\d{4})\b/.exec(label);
  return year ? { year: Number(year[1]), month: null } : null;
}

function endBeforeStart(start: string, end: string): boolean {
  if (!start || !end || PRESENT_RE.test(end)) return false;
  const a = dateOrder(start);
  const b = dateOrder(end);
  if (!a || !b) return false;
  if (a.month !== null && b.month !== null) return b.year * 12 + b.month < a.year * 12 + a.month;
  return b.year < a.year;
}

interface RangeState {
  start: DateValue;
  end: DateValue;
  current: boolean;
}

function rangeFrom(start: string, end: string): RangeState {
  const current = PRESENT_RE.test((end ?? "").trim());
  return { start: dateFromLabel(start), end: dateFromLabel(current ? "" : end), current };
}

function rangeLabels(range: RangeState): { start: string; end: string } {
  return { start: dateToLabel(range.start), end: range.current ? "Present" : dateToLabel(range.end) };
}

// ---------------------------------------------------------------------------
// Form models
// ---------------------------------------------------------------------------

const CONTACT_FIELDS: Array<{
  key: ContactFieldKey;
  label: string;
  type: "email" | "tel" | "text" | "url";
  autoComplete: string;
  placeholder: string;
  maxLength: number;
  inputMode?: HTMLAttributes<HTMLInputElement>["inputMode"];
}> = [
  { key: "email", label: "Email", type: "email", autoComplete: "email", placeholder: "name@example.com", maxLength: 200, inputMode: "email" },
  { key: "phone", label: "Phone", type: "tel", autoComplete: "tel", placeholder: "+91 98765 43210", maxLength: 40, inputMode: "tel" },
  { key: "location", label: "Location", type: "text", autoComplete: "address-level2", placeholder: "City, Country", maxLength: 120 },
  { key: "linkedin", label: "LinkedIn", type: "text", autoComplete: "url", placeholder: "linkedin.com/in/you", maxLength: 200, inputMode: "url" },
  { key: "github", label: "GitHub", type: "text", autoComplete: "url", placeholder: "github.com/you", maxLength: 200, inputMode: "url" },
  { key: "portfolio", label: "Portfolio", type: "text", autoComplete: "url", placeholder: "yourname.dev", maxLength: 200, inputMode: "url" },
];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const FIELD_MAX = 160;
const DATE_MAX = 40;
const DETAILS_MAX = 300;
/** Backend limit on `education` fixes per request (indexed edits + new rows). */
const MAX_EDUCATION_FIXES = 10;
/** Backend limit on `experience` fixes per request. */
const MAX_EXPERIENCE_FIXES = 30;
/** Highest entry index the fix API accepts (ExperienceFix / EducationFix `index`). */
const MAX_EXPERIENCE_INDEX = 50;
const MAX_EDUCATION_INDEX = 20;

interface ExpState {
  role: string;
  employer: string;
  location: string;
  range: RangeState;
}

type ExpLabels = Required<Omit<ExperienceFix, "index">>;
const EXP_KEYS = ["role", "employer", "location", "start", "end"] as const;

function expFromEntry(entry: ReviewEntry): ExpState {
  return {
    role: entry.role ?? "",
    employer: entry.employer ?? "",
    location: entry.location ?? "",
    range: rangeFrom(entry.start ?? "", entry.end ?? ""),
  };
}

function expLabels(state: ExpState): ExpLabels {
  return {
    role: state.role.trim(),
    employer: state.employer.trim(),
    location: state.location.trim(),
    ...rangeLabels(state.range),
  };
}

interface NewEduRow {
  id: string;
  degree: string;
  institution: string;
  location: string;
  details: string;
  range: RangeState;
}

function blankEduRow(id: string): NewEduRow {
  return { id, degree: "", institution: "", location: "", details: "", range: rangeFrom("", "") };
}

function isBlankEduRow(row: NewEduRow): boolean {
  const { start, end } = rangeLabels(row.range);
  return !row.degree.trim() && !row.institution.trim() && !row.location.trim() && !row.details.trim() && !start && !end;
}

function entryIssueMessage(issues: ReviewIssue[], index: number, codes: string[], fallback: string): string {
  return issues.find((i) => i.index === index && codes.includes(i.code))?.message ?? fallback;
}

function entryTitle(entry: ReviewEntry, fallback: string): string {
  return entry.role || entry.heading || fallback;
}

// ---------------------------------------------------------------------------
// Field components
// ---------------------------------------------------------------------------

interface TextFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  error?: string;
  hint?: ReactNode;
  warning?: boolean;
  /** The value won't be sent (e.g. an unticked profile suggestion). */
  muted?: boolean;
  /** Rendered next to the label (e.g. a "Use" checkbox). */
  labelAddon?: ReactNode;
  type?: "text" | "email" | "tel" | "url";
  placeholder?: string;
  autoComplete?: string;
  inputMode?: HTMLAttributes<HTMLInputElement>["inputMode"];
  maxLength?: number;
  className?: string;
}

function TextField({ label, value, onChange, onBlur, error, hint, warning, muted, labelAddon, type = "text", className, ...rest }: TextFieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className={LABEL}>
          {label}
        </label>
        {labelAddon}
      </div>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={cn(INPUT, warning && INPUT_WARNING, error && INPUT_ERROR, muted && "text-muted-foreground")}
        {...rest}
      />
      {hint && (
        <p id={hintId} className={cn("flex items-start gap-1 text-xs", warning ? "text-warning" : "text-muted-foreground")}>
          {warning && <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />}
          <span>{hint}</span>
        </p>
      )}
      {error && (
        <p id={errorId} className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

interface DateFieldProps {
  label: string;
  value: DateValue;
  onChange: (value: DateValue) => void;
  disabled?: boolean;
  error?: string;
  warning?: boolean;
  /** Extra ids for aria-describedby (e.g. the range's warning text). */
  describedBy?: string;
}

function DateField({ label, value, onChange, disabled, error, warning, describedBy }: DateFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const reasonId = `${id}-reason`;
  const monthSupported = useMonthInputSupported();
  const pickerMode = monthSupported && value.mode === "month";
  const text = value.text;
  const pickable = !text.trim() || !!labelToMonthInput(text);
  const showFormatHint = !pickerMode && !disabled && !looksLikeDate(text);
  const toggleBlocked = !pickerMode && !pickable;
  /** The picker's value when it gained focus (see onBlur); null when not focused. */
  const [textAtFocus, setTextAtFocus] = useState<string | null>(null);
  const canClear = !!text.trim() || !!textAtFocus?.trim();
  const inputRef = useRef<HTMLInputElement>(null);

  const clear = () => {
    setTextAtFocus(null);
    onChange({ ...value, text: "" });
    // The button disappears once the field is empty; keep focus in the field.
    // After the re-render, so the picker's onFocus records "" and its onBlur
    // doesn't restore the cleared month.
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const toggle = () => {
    if (value.mode === "month") {
      onChange({ mode: "text", text: dateToLabel(value) });
    } else if (pickable) {
      // Only month-precise (or empty) text can move into the picker; anything
      // else stays as typed so the original date is never lost.
      onChange({ mode: "month", text: value.text });
    }
  };
  const ariaDescribedBy =
    [describedBy, showFormatHint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  const inputClass = cn(INPUT, (warning || showFormatHint) && INPUT_WARNING, error && INPUT_ERROR);
  const linkButton =
    "rounded text-[11px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30";
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className={LABEL}>
          {label}
        </label>
        {!disabled && (
          <div className="flex items-center gap-2">
            {canClear && (
              <button
                type="button"
                onClick={clear}
                aria-label={`Clear ${label.toLowerCase()} date`}
                className={linkButton}
              >
                Clear
              </button>
            )}
            {monthSupported && (
              <button
                type="button"
                onClick={toggle}
                // aria-disabled (not disabled) keeps focus and the explanation reachable.
                aria-disabled={toggleBlocked || undefined}
                aria-describedby={toggleBlocked ? reasonId : undefined}
                className={cn(
                  linkButton,
                  "aria-disabled:cursor-not-allowed aria-disabled:opacity-50 aria-disabled:hover:no-underline",
                )}
              >
                {pickerMode ? "Type instead" : "Use month picker"}
              </button>
            )}
          </div>
        )}
      </div>
      {pickerMode ? (
        <input
          id={id}
          type="month"
          value={labelToMonthInput(text) ?? ""}
          onChange={(e) => {
            const v = e.target.value;
            // "" also while a segment is half-cleared; onBlur restores the
            // previous month unless the user cleared it with "Clear".
            onChange({ mode: "month", text: v ? monthInputToLabel(v) || v : "" });
          }}
          onFocus={() => setTextAtFocus(text)}
          onBlur={() => {
            const before = textAtFocus;
            setTextAtFocus(null);
            if (!text.trim() && before?.trim()) onChange({ mode: "month", text: before });
          }}
          ref={inputRef}
          disabled={disabled}
          placeholder="YYYY-MM"
          aria-invalid={error ? true : undefined}
          aria-describedby={ariaDescribedBy}
          className={inputClass}
        />
      ) : (
        <input
          id={id}
          type="text"
          value={text}
          onChange={(e) => onChange({ ...value, text: e.target.value })}
          ref={inputRef}
          disabled={disabled}
          placeholder="Jun 2025"
          maxLength={DATE_MAX}
          aria-invalid={error ? true : undefined}
          aria-describedby={ariaDescribedBy}
          className={inputClass}
        />
      )}
      {toggleBlocked && monthSupported && !disabled && (
        <p id={reasonId} className="text-[11px] text-muted-foreground">
          “{text.trim()}” isn’t a single month, so the month picker is off and it stays as typed.
        </p>
      )}
      {showFormatHint && (
        <p id={hintId} className="flex items-start gap-1 text-xs text-warning">
          <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
          <span>{DATE_FORMAT_HINT}.</span>
        </p>
      )}
      {error && (
        <p id={errorId} className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

const PRESENT_DISPLAY: DateValue = { mode: "text", text: "Present" };

interface DateRangeFieldsProps {
  range: RangeState;
  onChange: (range: RangeState) => void;
  currentLabel: string;
  endError?: string;
  warning?: boolean;
  warningText?: string;
}

function DateRangeFields({ range, onChange, currentLabel, endError, warning, warningText }: DateRangeFieldsProps) {
  const currentId = useId();
  const warningId = useId();
  const showWarning = !!warning && !!warningText;
  return (
    <div className="space-y-2 sm:col-span-2">
      {showWarning && (
        <p id={warningId} className="flex items-start gap-1 text-xs text-warning">
          <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
          <span>{warningText}</span>
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <DateField
          label="Start"
          value={range.start}
          warning={warning && !dateToLabel(range.start)}
          describedBy={showWarning ? warningId : undefined}
          onChange={(start) => onChange({ ...range, start })}
        />
        <DateField
          label="End"
          value={range.current ? PRESENT_DISPLAY : range.end}
          disabled={range.current}
          error={endError}
          describedBy={showWarning ? warningId : undefined}
          onChange={(end) => onChange({ ...range, end })}
        />
      </div>
      <div className="flex items-center gap-2">
        <input
          id={currentId}
          type="checkbox"
          checked={range.current}
          onChange={(e) => onChange({ ...range, current: e.target.checked })}
          className={CHECKBOX}
        />
        <label htmlFor={currentId} className="text-sm text-foreground">
          {currentLabel}
        </label>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// The form
// ---------------------------------------------------------------------------

interface ResumeFixFormProps extends ResumeFixPanelProps {
  headingRef: RefObject<HTMLHeadingElement | null>;
  /** Called after a fix result was applied (drives focus + announcement). */
  onApplied: () => void;
}

function ResumeFixForm({
  documentId,
  review,
  contactSuggestions,
  warnings,
  onFixed,
  getGeneration,
  disabled = false,
  headingRef,
  onApplied,
}: ResumeFixFormProps) {
  const headingId = useId();
  const contactRegionId = useId();
  const rememberId = useId();
  const contactHeadingId = useId();
  const expHeadingId = useId();
  const eduHeadingId = useId();
  const eduIdPrefix = useId();
  const eduSeq = useRef(0);
  const formRef = useRef<HTMLFormElement>(null);

  const issues: ReviewIssue[] = review?.issues ?? [];
  const reviewContact: Partial<ContactFields> = review?.contact ?? {};
  const suggestions: Partial<ContactFields> = contactSuggestions ?? {};
  const allExperience: ReviewEntry[] = review?.experience ?? [];
  const education: ReviewEntry[] = review?.education ?? [];
  // The fix API only addresses entries up to these indexes; later ones are
  // listed as a notice and can be changed with "Edit text".
  const experience = allExperience.filter((e) => e.index <= MAX_EXPERIENCE_INDEX);
  const uneditableExpCount = allExperience.length - experience.length;

  const hasContactIssue = issues.some((i) => i.code === "missing_email" || i.code === "missing_phone");
  const missingEducationIssue = issues.find((i) => i.code === "missing_education");
  const expWithIssues = experience.filter((e) => e.issues?.length);
  const allEduDateEntries = education.filter((e) => e.issues?.includes("missing_dates"));
  const eduDateEntries = allEduDateEntries.filter((e) => e.index <= MAX_EDUCATION_INDEX);
  const uneditableEduCount = allEduDateEntries.length - eduDateEntries.length;
  const openCount = countOpenIssues(review);
  const maxNewEdu = Math.max(0, MAX_EDUCATION_FIXES - eduDateEntries.length);

  /** Fields the resume lacks but the profile has: offered, not sent unless used. */
  const isSuggested = (key: ContactFieldKey) => !(reviewContact[key] ?? "").trim() && !!(suggestions[key] ?? "").trim();

  // --- state (initialised once; the parent re-keys us on a new review) ---
  const [contact, setContact] = useState<ContactFields>(() => {
    const out = {} as ContactFields;
    for (const f of CONTACT_FIELDS) out[f.key] = reviewContact[f.key] || suggestions[f.key] || "";
    return out;
  });
  // A suggestion is pre-ticked only when it closes an open issue.
  const [useSuggestion, setUseSuggestion] = useState<Partial<Record<ContactFieldKey, boolean>>>(() => ({
    email: isSuggested("email") && issues.some((i) => i.code === "missing_email"),
    phone: isSuggested("phone") && issues.some((i) => i.code === "missing_phone"),
  }));
  const [contactOpen, setContactOpen] = useState(false);
  const [showAllRoles, setShowAllRoles] = useState(false);
  const [initialExp] = useState<Record<number, ExpLabels>>(() =>
    Object.fromEntries(experience.map((e) => [e.index, expLabels(expFromEntry(e))])),
  );
  const [exp, setExp] = useState<Record<number, ExpState>>(() =>
    Object.fromEntries(experience.map((e) => [e.index, expFromEntry(e)])),
  );
  const [initialEduDates] = useState<Record<number, { start: string; end: string }>>(() =>
    Object.fromEntries(eduDateEntries.map((e) => [e.index, rangeLabels(rangeFrom(e.start ?? "", e.end ?? ""))])),
  );
  const [eduDates, setEduDates] = useState<Record<number, RangeState>>(() =>
    Object.fromEntries(eduDateEntries.map((e) => [e.index, rangeFrom(e.start ?? "", e.end ?? "")])),
  );
  const [newEdu, setNewEdu] = useState<NewEduRow[]>(() =>
    missingEducationIssue && maxNewEdu > 0 ? [blankEduRow(`${eduIdPrefix}-0`)] : [],
  );
  const [remember, setRemember] = useState(true);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [submitted, setSubmitted] = useState(false);
  const [invalidFocusRequest, setInvalidFocusRequest] = useState(0);

  const showContact = hasContactIssue || contactOpen;
  const visibleExp = showAllRoles ? experience : expWithIssues;
  const visibleExpIndexes = new Set(visibleExp.map((e) => e.index));
  const showEducation = !!missingEducationIssue || eduDateEntries.length > 0 || newEdu.length > 0;

  // --- derive payload + validation errors from ALL state (visible or not) ---
  const errors: Record<string, string> = {};
  const payload: ResumeFixPayload = { remember };
  let changeCount = 0;
  let hiddenChangeCount = 0;

  /** The value a contact field would send; an unused suggestion keeps the resume's value. */
  const effectiveContact = (key: ContactFieldKey) =>
    isSuggested(key) && !useSuggestion[key] ? (reviewContact[key] ?? "").trim() : contact[key].trim();

  const contactDiff: Partial<ContactFields> = {};
  for (const f of CONTACT_FIELDS) {
    const value = effectiveContact(f.key);
    if (value !== (reviewContact[f.key] ?? "").trim()) contactDiff[f.key] = value;
  }
  const email = effectiveContact("email");
  if (email && !EMAIL_RE.test(email)) errors["contact.email"] = "Enter a valid email address, e.g. name@example.com.";
  const phone = effectiveContact("phone");
  if (phone && phone.replace(/\D/g, "").length < 7) errors["contact.phone"] = "A phone number needs at least 7 digits.";
  const contactDiffCount = Object.keys(contactDiff).length;
  if (contactDiffCount) {
    payload.contact = contactDiff;
    changeCount += contactDiffCount;
    if (!showContact) hiddenChangeCount += contactDiffCount;
  }

  const expFixes: ExperienceFix[] = [];
  for (const entry of experience) {
    const state = exp[entry.index];
    const before = initialExp[entry.index];
    if (!state || !before) continue;
    const now = expLabels(state);
    const fix: ExperienceFix = { index: entry.index };
    let changed = 0;
    for (const key of EXP_KEYS) {
      if (now[key] !== before[key]) {
        fix[key] = now[key];
        changed += 1;
      }
    }
    if (endBeforeStart(now.start, now.end)) errors[`exp.${entry.index}.end`] = "End date can’t be before the start date.";
    if (changed) {
      expFixes.push(fix);
      changeCount += changed;
      if (!visibleExpIndexes.has(entry.index)) hiddenChangeCount += changed;
    }
  }
  if (expFixes.length) payload.experience = expFixes;
  const tooManyExpFixes = expFixes.length > MAX_EXPERIENCE_FIXES;

  const eduFixes: EducationFix[] = [];
  for (const entry of eduDateEntries) {
    const range = eduDates[entry.index];
    const before = initialEduDates[entry.index];
    if (!range || !before) continue;
    const now = rangeLabels(range);
    const fix: EducationFix = { index: entry.index };
    let changed = 0;
    if (now.start !== before.start) {
      fix.start = now.start;
      changed += 1;
    }
    if (now.end !== before.end) {
      fix.end = now.end;
      changed += 1;
    }
    if (endBeforeStart(now.start, now.end)) errors[`edu.${entry.index}.end`] = "End date can’t be before the start date.";
    if (changed) {
      eduFixes.push(fix);
      changeCount += changed;
    }
  }
  for (const row of newEdu) {
    if (isBlankEduRow(row)) continue;
    const dates = rangeLabels(row.range);
    const fix: EducationFix = {};
    if (row.degree.trim()) fix.degree = row.degree.trim();
    if (row.institution.trim()) fix.institution = row.institution.trim();
    if (row.location.trim()) fix.location = row.location.trim();
    if (dates.start) fix.start = dates.start;
    if (dates.end) fix.end = dates.end;
    if (row.details.trim()) fix.details = row.details.trim();
    if (!fix.degree && !fix.institution) errors[`new.${row.id}.degree`] = "Add the degree or the institution.";
    if (endBeforeStart(dates.start, dates.end)) errors[`new.${row.id}.end`] = "End date can’t be before the start date.";
    eduFixes.push(fix);
    changeCount += 1;
  }
  if (eduFixes.length) payload.education = eduFixes;

  const hasErrors = Object.keys(errors).length > 0;
  // Text inputs show errors after blur or a submit attempt; date-order and
  // required-row errors are only computed from complete values, so they show
  // immediately (date order) or after submit (required).
  const textError = (key: string) => (submitted || touched[key] ? errors[key] : undefined);
  const submitError = (key: string) => (submitted ? errors[key] : undefined);
  const touch = (key: string) => () => setTouched((t) => (t[key] ? t : { ...t, [key]: true }));

  // After a failed submit, move focus to the first invalid field once it renders.
  useEffect(() => {
    if (!invalidFocusRequest) return;
    formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
  }, [invalidFocusRequest]);

  // --- mutation (shares the page's "resume-tailored" key for busy tracking) ---
  // Callbacks live on the mutation options (not mutate()) so a result that
  // arrives after this form unmounted (tab switch, remount) is still applied.
  // They read the latest props through refs; onFixed is the page's
  // generation-guarded apply, which outlives this form.
  const onFixedRef = useRef(onFixed);
  const onAppliedRef = useRef(onApplied);
  useLayoutEffect(() => {
    onFixedRef.current = onFixed;
    onAppliedRef.current = onApplied;
  });
  const mutation = useMutation<TailoredResume, unknown, { body: ResumeFixPayload; generation: number }>({
    mutationKey: [...RESUME_TAILORED_KEY, "fix"],
    mutationFn: ({ body }) => postResumeFix(documentId, body),
    onSuccess: (data, variables) => {
      if (!onFixedRef.current(data, variables.generation)) return;
      toast.success("Resume updated");
      onAppliedRef.current();
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, "Could not update the resume"));
    },
  });

  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSubmitted(true);
    if (hasErrors) {
      // Reveal collapsed sections that hold an invalid field, then focus it.
      if (!showContact && Object.keys(errors).some((k) => k.startsWith("contact."))) setContactOpen(true);
      if (experience.some((entry) => errors[`exp.${entry.index}.end`] && !visibleExpIndexes.has(entry.index))) {
        setShowAllRoles(true);
      }
      setInvalidFocusRequest((n) => n + 1);
      return;
    }
    if (disabled || changeCount === 0 || tooManyExpFixes || mutation.isPending) return;
    setInvalidFocusRequest(0);
    mutation.mutate({ body: payload, generation: getGeneration() });
  };

  // --- state updaters ---
  const setExpField = (index: number, patch: Partial<ExpState>) =>
    setExp((prev) => ({ ...prev, [index]: { ...prev[index], ...patch } }));
  const setNewEduRow = (id: string, patch: Partial<NewEduRow>) =>
    setNewEdu((rows) => rows.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  const addEduRow = () => {
    eduSeq.current += 1;
    const id = `${eduIdPrefix}-${eduSeq.current}`;
    setNewEdu((rows) => (rows.length >= maxNewEdu ? rows : [...rows, blankEduRow(id)]));
  };

  const showFooter = showContact || visibleExp.length > 0 || showEducation || changeCount > 0;
  const hiddenRoleCount = experience.length - expWithIssues.length;
  const submitDisabled = disabled || mutation.isPending || changeCount === 0 || tooManyExpFixes;
  const addEduBlocked = newEdu.length >= maxNewEdu;
  const addEduReasonId = `${eduHeadingId}-add-reason`;

  return (
    <div className="space-y-4">
      <section aria-labelledby={headingId} className="rounded-3xl border border-border bg-card/60 p-6">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 id={headingId} ref={headingRef} tabIndex={-1} className="font-medium focus:outline-none">
              Fix resume gaps
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Add the details the Resume Agent couldn’t find. The PDF is regenerated with your facts — nothing is invented.
            </p>
          </div>
          {openCount > 0 ? (
            <span className="shrink-0 rounded-full bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning">
              {openCount} open {openCount === 1 ? "issue" : "issues"}
            </span>
          ) : (
            <span className="shrink-0 rounded-full bg-success/15 px-2.5 py-1 text-xs font-medium text-success">All set</span>
          )}
        </div>

        {openCount === 0 && (
          <div role="status" className="mt-4 flex items-start gap-2 rounded-2xl border border-success/30 bg-success/10 p-4 text-sm text-success">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>No missing details — your resume has contact info, dates and education.</span>
          </div>
        )}

        <form ref={formRef} noValidate onSubmit={onSubmit} className="mt-5 space-y-6">
          {/* Contact */}
          <div role="group" aria-labelledby={contactHeadingId} className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 id={contactHeadingId} className="text-sm font-medium">Contact details</h3>
              {!hasContactIssue && (
                <button
                  type="button"
                  aria-expanded={contactOpen}
                  aria-controls={contactRegionId}
                  onClick={() => setContactOpen((v) => !v)}
                  className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:bg-card focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                >
                  Edit contact
                  <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", contactOpen && "rotate-180")} aria-hidden="true" />
                </button>
              )}
            </div>
            {hasContactIssue && (
              <ul className="space-y-1 text-xs text-warning">
                {issues
                  .filter((i) => i.code === "missing_email" || i.code === "missing_phone")
                  .map((i) => (
                    <li key={i.code} className="flex items-start gap-1">
                      <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                      <span>{i.message}</span>
                    </li>
                  ))}
              </ul>
            )}
            {/* Always rendered (hidden when collapsed) so aria-controls has a target. */}
            <div
              id={contactRegionId}
              hidden={!showContact}
              className={showContact ? "grid gap-3 sm:grid-cols-2" : "hidden"}
            >
              {CONTACT_FIELDS.map((f) => {
                const suggested = isSuggested(f.key);
                const used = !!useSuggestion[f.key];
                // Once the user edits a suggestion it's their own value, not the profile's.
                const edited = suggested && contact[f.key].trim() !== (suggestions[f.key] ?? "").trim();
                const missing = !effectiveContact(f.key) && issues.some((i) => i.code === `missing_${f.key}`);
                return (
                  <TextField
                    key={f.key}
                    label={f.label}
                    type={f.type}
                    value={contact[f.key]}
                    onChange={(v) => {
                      setContact((c) => ({ ...c, [f.key]: v }));
                      // Typing into a suggestion means the user wants it.
                      if (suggested) setUseSuggestion((u) => (u[f.key] ? u : { ...u, [f.key]: true }));
                    }}
                    onBlur={touch(`contact.${f.key}`)}
                    error={textError(`contact.${f.key}`)}
                    hint={
                      suggested
                        ? !used
                          ? "Not included — tick Use to add it."
                          : edited
                            ? undefined
                            : "From your profile — will be added."
                        : undefined
                    }
                    muted={suggested && !used}
                    warning={missing}
                    labelAddon={
                      suggested ? (
                        <label className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                          <input
                            type="checkbox"
                            checked={used}
                            onChange={(e) => setUseSuggestion((u) => ({ ...u, [f.key]: e.target.checked }))}
                            aria-label={
                              edited
                                ? `Include this ${f.label.toLowerCase()}`
                                : `Use the ${f.label.toLowerCase()} from your profile`
                            }
                            className="h-3.5 w-3.5 shrink-0 rounded border-border accent-primary"
                          />
                          Use
                        </label>
                      ) : null
                    }
                    placeholder={f.placeholder}
                    autoComplete={f.autoComplete}
                    inputMode={f.inputMode}
                    maxLength={f.maxLength}
                  />
                );
              })}
              <p className="text-xs text-muted-foreground sm:col-span-2">Clear a field to remove it from the contact line.</p>
            </div>
          </div>

          {/* Experience */}
          {experience.length > 0 && (
            <div role="group" aria-labelledby={expHeadingId} className="space-y-3 border-t border-border pt-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 id={expHeadingId} className="text-sm font-medium">Experience</h3>
                {hiddenRoleCount > 0 && (
                  <button
                    type="button"
                    aria-pressed={showAllRoles}
                    onClick={() => setShowAllRoles((v) => !v)}
                    className={cn(
                      "rounded-full px-3 py-1 text-xs transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30",
                      showAllRoles ? "bg-primary/10 font-medium text-primary" : "border border-border text-muted-foreground hover:bg-card",
                    )}
                  >
                    {showAllRoles ? "Show roles with issues" : "Edit all roles"}
                  </button>
                )}
              </div>
              {visibleExp.length === 0 && (
                <p className="text-sm text-muted-foreground">Every role has an employer and dates.</p>
              )}
              {uneditableExpCount > 0 && (
                <p className="flex items-start gap-1 text-xs text-muted-foreground">
                  <Info className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                  <span>
                    {uneditableExpCount} more {uneditableExpCount === 1 ? "role isn’t" : "roles aren’t"} listed here
                    (only the first {MAX_EXPERIENCE_INDEX + 1} can be fixed in this form) — use Edit text to change{" "}
                    {uneditableExpCount === 1 ? "it" : "them"}.
                  </span>
                </p>
              )}
              {visibleExp.map((entry, n) => {
                const state = exp[entry.index];
                if (!state) return null;
                const employerIssue = entry.issues.includes("missing_employer")
                  ? entryIssueMessage(issues, entry.index, ["missing_employer"], "The employer is missing.")
                  : entry.issues.includes("truncated_employer")
                    ? entryIssueMessage(issues, entry.index, ["truncated_employer"], "The employer name looks cut off — enter the full name.")
                    : undefined;
                const datesIssue = entry.issues.includes("missing_dates")
                  ? entryIssueMessage(issues, entry.index, ["missing_dates"], "Add start and end dates.")
                  : undefined;
                return (
                  <div key={entry.index} className={SUB_CARD}>
                    <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                      <div className="text-sm font-medium">{entryTitle(entry, `Role ${n + 1}`)}</div>
                      {entry.section && <div className="text-xs uppercase tracking-wide text-muted-foreground">{entry.section}</div>}
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <TextField
                        label="Role"
                        value={state.role}
                        onChange={(role) => setExpField(entry.index, { role })}
                        placeholder="Software Engineer"
                        maxLength={FIELD_MAX}
                      />
                      <TextField
                        label="Employer"
                        value={state.employer}
                        onChange={(employer) => setExpField(entry.index, { employer })}
                        warning={!!employerIssue}
                        hint={employerIssue}
                        placeholder="Company legal name"
                        autoComplete="organization"
                        maxLength={FIELD_MAX}
                      />
                      <TextField
                        label="Location"
                        value={state.location}
                        onChange={(location) => setExpField(entry.index, { location })}
                        placeholder="City, Country or Remote"
                        maxLength={FIELD_MAX}
                        className="sm:col-span-2"
                      />
                      <DateRangeFields
                        range={state.range}
                        onChange={(range) => setExpField(entry.index, { range })}
                        currentLabel="I currently work here"
                        endError={errors[`exp.${entry.index}.end`]}
                        warning={!!datesIssue}
                        warningText={datesIssue}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Education */}
          <div role="group" aria-labelledby={eduHeadingId} className="space-y-3 border-t border-border pt-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 id={eduHeadingId} className="text-sm font-medium">Education</h3>
              <button
                type="button"
                onClick={addEduRow}
                // aria-disabled (not disabled) keeps the button and its reason reachable.
                aria-disabled={addEduBlocked || undefined}
                aria-describedby={addEduBlocked ? addEduReasonId : undefined}
                className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:bg-card focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 aria-disabled:cursor-not-allowed aria-disabled:opacity-60"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                Add education
              </button>
            </div>
            {addEduBlocked && (
              <p id={addEduReasonId} className="text-xs text-muted-foreground">
                {maxNewEdu === 0
                  ? `Up to ${MAX_EDUCATION_FIXES} education changes can be sent at a time — add the dates below first.`
                  : `You can add up to ${maxNewEdu} education ${maxNewEdu === 1 ? "entry" : "entries"} at a time.`}
              </p>
            )}
            {uneditableEduCount > 0 && (
              <p className="flex items-start gap-1 text-xs text-muted-foreground">
                <Info className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                <span>
                  {uneditableEduCount} more education {uneditableEduCount === 1 ? "entry needs" : "entries need"} dates
                  but {uneditableEduCount === 1 ? "isn’t" : "aren’t"} listed here (only the first{" "}
                  {MAX_EDUCATION_INDEX + 1} can be fixed in this form) — use Edit text.
                </span>
              </p>
            )}
            {missingEducationIssue && (
              <p className="flex items-start gap-1 text-xs text-warning">
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                <span>
                  {missingEducationIssue.message}
                  {!review?.has_education_section && " An Education section will be added."}
                </span>
              </p>
            )}
            {!showEducation && uneditableEduCount === 0 && (
              <p className="text-sm text-muted-foreground">Your education entries have dates.</p>
            )}

            {eduDateEntries.map((entry, n) => {
              const range = eduDates[entry.index];
              if (!range) return null;
              const title = [entry.role, entry.employer].filter(Boolean).join(" — ") || entry.heading || `Education ${n + 1}`;
              return (
                <div key={`edu-${entry.index}`} className={SUB_CARD}>
                  <div className="mb-3 text-sm font-medium">{title}</div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <DateRangeFields
                      range={range}
                      onChange={(next) => setEduDates((prev) => ({ ...prev, [entry.index]: next }))}
                      currentLabel="I’m currently studying here"
                      endError={errors[`edu.${entry.index}.end`]}
                      warning
                      warningText="Add the start and graduation dates."
                    />
                  </div>
                </div>
              );
            })}

            {newEdu.map((row, n) => (
              <div key={row.id} className={SUB_CARD}>
                <div className="mb-3 flex items-center justify-between gap-2">
                  <div className="text-sm font-medium">New education entry{newEdu.length > 1 ? ` ${n + 1}` : ""}</div>
                  <button
                    type="button"
                    onClick={() => setNewEdu((rows) => rows.filter((r) => r.id !== row.id))}
                    aria-label={`Remove new education entry ${n + 1}`}
                    className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-card hover:text-danger focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
                  >
                    <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                    Remove
                  </button>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <TextField
                    label="Degree"
                    value={row.degree}
                    onChange={(degree) => setNewEduRow(row.id, { degree })}
                    error={submitError(`new.${row.id}.degree`)}
                    placeholder="B.Tech, Computer Science"
                    maxLength={FIELD_MAX}
                  />
                  <TextField
                    label="Institution"
                    value={row.institution}
                    onChange={(institution) => setNewEduRow(row.id, { institution })}
                    placeholder="University or college"
                    autoComplete="organization"
                    maxLength={FIELD_MAX}
                  />
                  <TextField
                    label="Location"
                    value={row.location}
                    onChange={(location) => setNewEduRow(row.id, { location })}
                    placeholder="City, Country"
                    maxLength={FIELD_MAX}
                    className="sm:col-span-2"
                  />
                  <DateRangeFields
                    range={row.range}
                    onChange={(range) => setNewEduRow(row.id, { range })}
                    currentLabel="I’m currently studying here"
                    endError={errors[`new.${row.id}.end`]}
                  />
                  <TextField
                    label="Details"
                    value={row.details}
                    onChange={(details) => setNewEduRow(row.id, { details })}
                    placeholder="CGPA 8.6/10, First Class with Distinction"
                    hint="Optional — CGPA, honours, relevant coursework."
                    maxLength={DETAILS_MAX}
                    className="sm:col-span-2"
                  />
                </div>
              </div>
            ))}
          </div>

          {/* Footer */}
          {showFooter && (
            <div className="space-y-3 border-t border-border pt-5">
              <div className="flex items-center gap-2">
                <input
                  id={rememberId}
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  className={CHECKBOX}
                />
                <label htmlFor={rememberId} className="text-sm text-foreground">
                  Remember these details for future resumes
                </label>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <LiquidGlassButton
                  type="submit"
                  tone="primary"
                  size="sm"
                  disabled={submitDisabled}
                  aria-busy={mutation.isPending || undefined}
                >
                  {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
                  {mutation.isPending ? "Regenerating…" : "Apply & regenerate PDF"}
                </LiquidGlassButton>
                <p className={cn("text-xs", (submitted && hasErrors) || tooManyExpFixes ? "text-danger" : "text-muted-foreground")}>
                  {submitted && hasErrors
                    ? "Fix the highlighted fields before applying."
                    : tooManyExpFixes
                      ? `Up to ${MAX_EXPERIENCE_FIXES} roles can be changed at a time — undo some changes, apply, then continue.`
                      : disabled && !mutation.isPending
                        ? "Wait for the current resume update to finish."
                        : changeCount === 0
                          ? "Make a change to enable."
                          : `${changeCount} ${changeCount === 1 ? "change" : "changes"} ready.`}
                </p>
                {/* Announced once per failed submit, not on every keystroke;
                    success is announced by the "Resume updated" toast. */}
                <p aria-live="polite" className="sr-only">
                  {invalidFocusRequest > 0 ? (
                    <span key={invalidFocusRequest}>Fix the highlighted fields before applying.</span>
                  ) : null}
                </p>
                {hiddenChangeCount > 0 && (
                  <p className="text-xs text-warning">
                    {hiddenChangeCount} unsaved {hiddenChangeCount === 1 ? "change" : "changes"} (hidden)
                  </p>
                )}
              </div>
            </div>
          )}
        </form>
      </section>

      {warnings.length > 0 && (
        <section aria-label="Notes from the Resume Agent" className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-warning" aria-hidden="true" />
            <h2 className="text-sm font-medium">Notes from the Resume Agent</h2>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            These can’t be fixed by editing — they’re genuine gaps versus the job. Address them in a cover letter or by building the skill.
          </p>
          <ul className="mt-3 space-y-2">
            {warnings.map((warning, i) => (
              <li key={`${i}-${warning}`} className="rounded-xl bg-warning/10 px-3 py-2 text-sm text-warning">
                {warning}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
