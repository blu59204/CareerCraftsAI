"use client";

import { useId, useState, type FormEvent, type HTMLAttributes, type ReactNode } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2, ChevronDown, Info, Loader2, Plus, Trash2 } from "lucide-react";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { apiClient, getApiErrorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import type {
  ContactFieldKey,
  ContactFields,
  EducationFix,
  ExperienceFix,
  ResumeFixPayload,
  ResumeReview,
  ReviewEntry,
  ReviewIssue,
  TailoredResume,
} from "@/lib/resume-types";

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export interface ResumeFixPanelProps {
  documentId: string;
  review: ResumeReview;
  contactSuggestions: Partial<ContactFields>;
  warnings: string[];
  onFixed: (r: TailoredResume) => void;
}

/**
 * Form that lets the user fill the gaps the Resume Agent found (contact line,
 * employer names, dates, education) and re-render the tailored PDF.
 *
 * Form state is reset whenever a new review arrives (e.g. after a successful
 * fix) by keying the inner form on the document id + review contents.
 */
export function ResumeFixPanel(props: ResumeFixPanelProps) {
  const formKey = `${props.documentId}:${JSON.stringify(props.review ?? null)}:${JSON.stringify(props.contactSuggestions ?? {})}`;
  return <ResumeFixForm key={formKey} {...props} />;
}

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

/** "2025-06" -> "Jun 2025"; "" for anything else. */
function monthInputToLabel(value: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(value);
  if (!m) return "";
  const month = Number(m[2]);
  if (month < 1 || month > 12) return "";
  return `${MONTHS[month - 1]} ${m[1]}`;
}

function toMonthInput(year: string, month: number): string | null {
  if (month < 1 || month > 12) return null;
  return `${year}-${String(month).padStart(2, "0")}`;
}

/** "Jun 2025" / "June 2025" / "2025-06" / "06/2025" -> "2025-06"; null if not month-precise. */
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

/** A date field is a month picker unless the stored value can't be read as a month. */
interface DateValue {
  mode: "month" | "text";
  month: string; // "YYYY-MM" (month mode)
  text: string; // free text (text mode)
}

function dateFromLabel(raw: string): DateValue {
  const text = (raw ?? "").trim();
  if (!text) return { mode: "month", month: "", text: "" };
  const month = labelToMonthInput(text);
  return month ? { mode: "month", month, text } : { mode: "text", month: "", text };
}

function dateToLabel(value: DateValue): string {
  return value.mode === "month" ? monthInputToLabel(value.month) : value.text.trim();
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
  id: number;
  degree: string;
  institution: string;
  location: string;
  details: string;
  range: RangeState;
}

let eduRowSeq = 0;
function blankEduRow(): NewEduRow {
  eduRowSeq += 1;
  return { id: eduRowSeq, degree: "", institution: "", location: "", details: "", range: rangeFrom("", "") };
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
  type?: "text" | "email" | "tel" | "url";
  placeholder?: string;
  autoComplete?: string;
  inputMode?: HTMLAttributes<HTMLInputElement>["inputMode"];
  maxLength?: number;
  className?: string;
}

function TextField({ label, value, onChange, onBlur, error, hint, warning, type = "text", className, ...rest }: TextFieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cn("space-y-1", className)}>
      <label htmlFor={id} className={LABEL}>
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={cn(INPUT, warning && INPUT_WARNING, error && INPUT_ERROR)}
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
}

function DateField({ label, value, onChange, disabled, error, warning }: DateFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const isText = value.mode === "text";
  const toggle = () => {
    if (value.mode === "month") {
      onChange({ mode: "text", month: value.month, text: dateToLabel(value) });
    } else {
      onChange({ mode: "month", month: labelToMonthInput(value.text) ?? "", text: value.text });
    }
  };
  const describedBy = [isText && !disabled ? hintId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  const inputClass = cn(INPUT, warning && INPUT_WARNING, error && INPUT_ERROR);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className={LABEL}>
          {label}
        </label>
        {!disabled && (
          <button
            type="button"
            onClick={toggle}
            className="rounded text-[11px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
          >
            {isText ? "Use month picker" : "Type instead"}
          </button>
        )}
      </div>
      {isText ? (
        <input
          id={id}
          type="text"
          value={value.text}
          onChange={(e) => onChange({ ...value, text: e.target.value })}
          disabled={disabled}
          placeholder="Jun 2025"
          maxLength={DATE_MAX}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={inputClass}
        />
      ) : (
        <input
          id={id}
          type="month"
          value={value.month}
          onChange={(e) => onChange({ ...value, month: e.target.value })}
          disabled={disabled}
          placeholder="YYYY-MM"
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={inputClass}
        />
      )}
      {isText && !disabled && (
        <p id={hintId} className="text-xs text-muted-foreground">
          Use the format Mon YYYY, e.g. Jun 2025.
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

const PRESENT_DISPLAY: DateValue = { mode: "text", month: "", text: "Present" };

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
  return (
    <div className="space-y-2 sm:col-span-2">
      {warning && warningText && (
        <p className="flex items-start gap-1 text-xs text-warning">
          <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
          <span>{warningText}</span>
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <DateField
          label="Start"
          value={range.start}
          warning={warning && !dateToLabel(range.start)}
          onChange={(start) => onChange({ ...range, start })}
        />
        <DateField
          label="End"
          value={range.current ? PRESENT_DISPLAY : range.end}
          disabled={range.current}
          error={endError}
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

function ResumeFixForm({ documentId, review, contactSuggestions, warnings, onFixed }: ResumeFixPanelProps) {
  const headingId = useId();
  const contactRegionId = useId();
  const rememberId = useId();
  const contactHeadingId = useId();
  const expHeadingId = useId();
  const eduHeadingId = useId();

  const issues: ReviewIssue[] = review?.issues ?? [];
  const reviewContact: Partial<ContactFields> = review?.contact ?? {};
  const suggestions: Partial<ContactFields> = contactSuggestions ?? {};
  const experience: ReviewEntry[] = review?.experience ?? [];
  const education: ReviewEntry[] = review?.education ?? [];

  const hasContactIssue = issues.some((i) => i.code === "missing_email" || i.code === "missing_phone");
  const missingEducationIssue = issues.find((i) => i.code === "missing_education");
  const expWithIssues = experience.filter((e) => e.issues?.length);
  const eduDateEntries = education.filter((e) => e.issues?.includes("missing_dates"));
  const openCount = issues.length + eduDateEntries.length;

  // --- state (initialised once; the parent re-keys us on a new review) ---
  const [contact, setContact] = useState<ContactFields>(() => {
    const out = {} as ContactFields;
    for (const f of CONTACT_FIELDS) out[f.key] = reviewContact[f.key] || suggestions[f.key] || "";
    return out;
  });
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
  const [newEdu, setNewEdu] = useState<NewEduRow[]>(() => (missingEducationIssue ? [blankEduRow()] : []));
  const [remember, setRemember] = useState(true);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [submitted, setSubmitted] = useState(false);

  const showContact = hasContactIssue || contactOpen;
  const visibleExp = showAllRoles ? experience : expWithIssues;
  const showEducation = !!missingEducationIssue || eduDateEntries.length > 0 || newEdu.length > 0;

  // --- derive payload + validation errors from the current state ---
  const errors: Record<string, string> = {};
  const payload: ResumeFixPayload = { remember };
  let changeCount = 0;

  if (showContact) {
    const diff: Partial<ContactFields> = {};
    for (const f of CONTACT_FIELDS) {
      const value = contact[f.key].trim();
      if (value !== (reviewContact[f.key] ?? "").trim()) diff[f.key] = value;
    }
    const email = contact.email.trim();
    if (email && !EMAIL_RE.test(email)) errors["contact.email"] = "Enter a valid email address, e.g. name@example.com.";
    const phone = contact.phone.trim();
    if (phone && phone.replace(/\D/g, "").length < 7) errors["contact.phone"] = "A phone number needs at least 7 digits.";
    const diffCount = Object.keys(diff).length;
    if (diffCount) {
      payload.contact = diff;
      changeCount += diffCount;
    }
  }

  const expFixes: ExperienceFix[] = [];
  for (const entry of visibleExp) {
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
    }
  }
  if (expFixes.length) payload.experience = expFixes;

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

  // --- mutation ---
  const mutation = useMutation<TailoredResume, unknown, ResumeFixPayload>({
    mutationFn: async (body) => {
      const { data } = await apiClient.post<TailoredResume>(`/resume/tailored/${documentId}/fix`, body, {
        timeout: 60_000,
      });
      return data;
    },
    onSuccess: (data) => {
      toast.success("Resume updated");
      onFixed(data);
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, "Could not update the resume"));
    },
  });

  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSubmitted(true);
    if (hasErrors || changeCount === 0 || mutation.isPending) return;
    mutation.mutate(payload);
  };

  // --- state updaters ---
  const setExpField = (index: number, patch: Partial<ExpState>) =>
    setExp((prev) => ({ ...prev, [index]: { ...prev[index], ...patch } }));
  const setNewEduRow = (id: number, patch: Partial<NewEduRow>) =>
    setNewEdu((rows) => rows.map((r) => (r.id === id ? { ...r, ...patch } : r)));

  const showFooter = showContact || visibleExp.length > 0 || showEducation;
  const hiddenRoleCount = experience.length - expWithIssues.length;

  return (
    <div className="space-y-4">
      <section aria-labelledby={headingId} className="rounded-3xl border border-border bg-card/60 p-6">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 id={headingId} className="font-medium">
              Fix resume gaps
            </h3>
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

        <form noValidate onSubmit={onSubmit} className="mt-5 space-y-6">
          {/* Contact */}
          <div role="group" aria-labelledby={contactHeadingId} className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 id={contactHeadingId} className="text-sm font-medium">Contact details</h4>
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
            {showContact && (
              <div id={contactRegionId} className="grid gap-3 sm:grid-cols-2">
                {CONTACT_FIELDS.map((f) => {
                  const fromProfile =
                    !reviewContact[f.key] && !!suggestions[f.key] && contact[f.key] === suggestions[f.key];
                  const missing = !contact[f.key].trim() && issues.some((i) => i.code === `missing_${f.key}`);
                  return (
                    <TextField
                      key={f.key}
                      label={f.label}
                      type={f.type}
                      value={contact[f.key]}
                      onChange={(v) => setContact((c) => ({ ...c, [f.key]: v }))}
                      onBlur={touch(`contact.${f.key}`)}
                      error={textError(`contact.${f.key}`)}
                      hint={fromProfile ? "from your profile" : undefined}
                      warning={missing}
                      placeholder={f.placeholder}
                      autoComplete={f.autoComplete}
                      inputMode={f.inputMode}
                      maxLength={f.maxLength}
                    />
                  );
                })}
                <p className="text-xs text-muted-foreground sm:col-span-2">Clear a field to remove it from the contact line.</p>
              </div>
            )}
          </div>

          {/* Experience */}
          {experience.length > 0 && (
            <div role="group" aria-labelledby={expHeadingId} className="space-y-3 border-t border-border pt-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h4 id={expHeadingId} className="text-sm font-medium">Experience</h4>
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
              <h4 id={eduHeadingId} className="text-sm font-medium">Education</h4>
              <button
                type="button"
                onClick={() => setNewEdu((rows) => [...rows, blankEduRow()])}
                className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:bg-card focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                Add education
              </button>
            </div>
            {missingEducationIssue && (
              <p className="flex items-start gap-1 text-xs text-warning">
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                <span>
                  {missingEducationIssue.message}
                  {!review?.has_education_section && " An Education section will be added."}
                </span>
              </p>
            )}
            {!showEducation && (
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
                  <div className="text-sm font-medium">New education entry {newEdu.length > 1 ? n + 1 : ""}</div>
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
                  disabled={mutation.isPending || changeCount === 0}
                  aria-busy={mutation.isPending || undefined}
                >
                  {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
                  {mutation.isPending ? "Regenerating…" : "Apply & regenerate PDF"}
                </LiquidGlassButton>
                <p aria-live="polite" className={cn("text-xs", submitted && hasErrors ? "text-danger" : "text-muted-foreground")}>
                  {submitted && hasErrors
                    ? "Fix the highlighted fields before applying."
                    : changeCount === 0
                      ? "Make a change to enable."
                      : `${changeCount} ${changeCount === 1 ? "change" : "changes"} ready.`}
                </p>
              </div>
            </div>
          )}
        </form>
      </section>

      {warnings.length > 0 && (
        <section aria-label="Notes from the Resume Agent" className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-warning" aria-hidden="true" />
            <h3 className="text-sm font-medium">Notes from the Resume Agent</h3>
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
