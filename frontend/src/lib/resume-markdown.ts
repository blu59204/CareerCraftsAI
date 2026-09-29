/**
 * Pure parser for the Markdown resumes the Resume Agent writes.
 *
 * Mirrors backend/app/services/resume_structure.py (heading split, placeholder
 * cleanup) and the line classification in backend/app/services/pdf_service.py
 * so the HTML preview lays out exactly what the PDF renderer will draw:
 *
 *   # Full Name
 *   email | phone | City, Country | linkedin.com/in/x
 *   ## SECTION
 *   ### Role | Employer | Location | Mon YYYY - Mon YYYY
 *   - bullet
 *   **Group:** item, item
 */

export type ResumeTemplateId = "modern" | "classic" | "technical";

export type ResumeItem =
  | { kind: "entry"; role: string; employer: string; location: string; dates: string }
  | { kind: "bullet"; text: string }
  | { kind: "text"; text: string };

export type ResumeSection = { title: string; items: ResumeItem[] };

export type ParsedResume = {
  name: string;
  headline: string[];
  contact: string[];
  /** A section with title "" holds body content that appears before any heading. */
  sections: ResumeSection[];
};

export type HeadingParts = {
  role: string;
  employer: string;
  location: string;
  start: string;
  end: string;
};

export type InlineToken = { text: string; bold: boolean; italic: boolean };

// ── Vocabulary (kept in sync with the backend) ─────────────────────────────

const SECTIONS = new Set([
  "summary", "professional summary", "profile", "objective", "experience",
  "work experience", "professional experience", "employment", "work history",
  "education", "skills", "technical skills", "technologies", "projects",
  "certifications", "awards", "publications", "languages", "volunteer experience",
  "internships", "achievements", "core competencies",
]);

const HEADING = /^(#{1,6})\s+/;
const BULLET = /^(?:[-*•]|\d+[.)])\s+/;
const YEAR = /\b(?:19|20)\d{2}\b/;
const DATE_WORD = /\b(?:present|current|now|ongoing)\b/i;
const ENTRY_DATE = /\b(?:19|20)\d{2}\b|\b(?:present|current)\b/i;
const RANGE_SPLIT = /\s*(?:\s-\s|–|—|\bto\b|-(?=\s*(?:\d|present|current|now)))\s*/i;
const PLACEHOLDER = /^\W*(?:not[_ ]provided|n\/?a|tbd|unknown)\W*$/i;
const PLACEHOLDER_INLINE = /\[?\(?\bNOT[_ ]PROVIDED\b\)?\]?/gi;
const CONTACT_HINT = /@|(?:\+?\d[\d\s().-]{7,})|(?:linkedin|github)\.com|https?:\/\//i;
const CONTACT_SPLIT = /\s*[|·•]\s*/;
const LIST_SEPARATORS = /[,;|/]/;
const RULE_LINES = new Set(["---", "***", "___"]);

function splitLines(value: string): string[] {
  return value.split(/\r\n|\r|\n/);
}

/** Strip Markdown emphasis/code markers (backend `_plain`). */
function plain(value: string): string {
  return value.replace(/[*_`]/g, "").trim();
}

function isPlaceholder(value: string): boolean {
  const v = value.trim();
  if (!v) return false;
  // Check with and without markers: `_plain` would turn NOT_PROVIDED into NOTPROVIDED.
  return PLACEHOLDER.test(v) || PLACEHOLDER.test(plain(v));
}

function looksLikeDates(value: string): boolean {
  return YEAR.test(value) || DATE_WORD.test(value);
}

function isUpperCase(value: string): boolean {
  // Python str.isupper(): at least one cased character and none lowercase.
  return value !== value.toLowerCase() && value === value.toUpperCase();
}

// ── Placeholder cleanup (backend `clean_placeholders`) ─────────────────────

function cleanPlaceholders(markdown: string): string[] {
  const out: string[] = [];
  for (const raw of splitLines(markdown)) {
    let line = raw.trimEnd();
    const stripped = line.trim();
    const heading = HEADING.exec(stripped);
    if (heading && stripped.includes("|")) {
      const parts = stripped
        .slice(heading[0].length)
        .split("|")
        .map((p) => p.trim())
        .filter((p) => p && !isPlaceholder(p));
      if (!parts.length) continue;
      line = `${heading[1]} ${parts.join(" | ")}`;
    } else if (!heading && stripped.includes("|")) {
      const parts = stripped.split("|").map((p) => p.trim());
      const kept = parts.filter((p) => p && !isPlaceholder(p));
      if (!kept.length) continue;
      if (kept.length !== parts.length) line = kept.join(" | ");
    }
    const body = line.trim().replace(HEADING, "").replace(BULLET, "");
    if (body && isPlaceholder(body)) continue;
    line = line.replace(PLACEHOLDER_INLINE, "").trimEnd();
    line = line.trim() ? line.replace(/\s{2,}/g, " ") : "";
    if (!line.trim() && raw.trim()) continue;
    out.push(line);
  }

  // Drop `##` headings with nothing under them before the next `##`.
  const result: string[] = [];
  out.forEach((line, i) => {
    const m = HEADING.exec(line.trim());
    if (m && m[1].length === 2) {
      const next = out.slice(i + 1).find((ln) => ln.trim());
      const nm = next ? HEADING.exec(next.trim()) : null;
      if (next === undefined || (nm && nm[1].length <= 2)) return;
    }
    result.push(line);
  });
  return result;
}

// ── Heading parts ───────────────────────────────────────────────────────────

function splitDates(value: string): [string, string] {
  const m = RANGE_SPLIT.exec(value);
  if (m) {
    const start = value.slice(0, m.index).trim();
    const end = value.slice(m.index + m[0].length).trim();
    if (start && end) return [start, end];
  }
  return [value.trim(), ""];
}

/** `Role | Employer | Location | Dates` → parts (any part may be absent). */
export function splitHeading(text: string): HeadingParts {
  const parts = plain(text)
    .split("|")
    .map((p) => p.trim())
    .filter((p) => p && !isPlaceholder(p));
  let dates = "";
  if (parts.length && looksLikeDates(parts[parts.length - 1])) {
    dates = parts.pop() ?? "";
  }
  const [start, end] = dates ? splitDates(dates) : ["", ""];
  return {
    role: parts[0] ?? "",
    employer: parts[1] ?? "",
    location: parts.slice(2).join(", "),
    start,
    end,
  };
}

/** "Jun 2025", "Present" → "Jun 2025 – Present" (either side may be empty). */
export function formatDates(start: string, end: string): string {
  const s = (start ?? "").trim();
  const e = (end ?? "").trim();
  if (s && e) return `${s} – ${e}`;
  return (s || e).replace(/\s*-\s*/g, " – ");
}

// ── Inline emphasis ─────────────────────────────────────────────────────────

function isWordChar(ch: string): boolean {
  return /\w/.test(ch);
}

function isSpace(ch: string): boolean {
  return /\s/.test(ch);
}

/** Single-`*` italics with the backend's boundary rules; unmatched `*` stay literal. */
function tokenizeItalic(text: string, bold: boolean): InlineToken[] {
  const tokens: InlineToken[] = [];
  let buffer = "";
  let i = 0;
  while (i < text.length) {
    const prev = i > 0 ? text[i - 1] : "";
    const next = text[i + 1] ?? "";
    const opens =
      text[i] === "*" && !isWordChar(prev) && prev !== "*" && next !== "" && !isSpace(next);
    let close = -1;
    if (opens) {
      for (let j = i + 2; j < text.length; j++) {
        if (text[j] !== "*") continue;
        const after = text[j + 1] ?? "";
        if (!isSpace(text[j - 1]) && !isWordChar(after) && after !== "*") {
          close = j;
          break;
        }
      }
    }
    if (close > 0) {
      if (buffer) tokens.push({ text: buffer, bold, italic: false });
      buffer = "";
      tokens.push({ text: text.slice(i + 1, close), bold, italic: true });
      i = close + 1;
    } else {
      buffer += text[i];
      i += 1;
    }
  }
  if (buffer) tokens.push({ text: buffer, bold, italic: false });
  return tokens;
}

/**
 * Split text with **bold** and *italic* into plain tokens for safe rendering
 * (no HTML is produced). Links become "label (url)"; backticks are dropped.
 */
export function tokenizeInline(value: string): InlineToken[] {
  const text = value
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1 ($2)")
    .replace(/`/g, "");
  const tokens: InlineToken[] = [];
  const bold = /\*\*(.+?)\*\*/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = bold.exec(text)) !== null) {
    if (m.index > last) {
      tokens.push(...tokenizeItalic(text.slice(last, m.index).replace(/\*\*/g, ""), false));
    }
    tokens.push(...tokenizeItalic(m[1], true));
    last = m.index + m[0].length;
  }
  if (last < text.length) {
    tokens.push(...tokenizeItalic(text.slice(last).replace(/\*\*/g, ""), false));
  }
  return tokens;
}

// ── Document ────────────────────────────────────────────────────────────────

function entryItem(line: string): ResumeItem {
  const parts = splitHeading(line);
  if (!parts.role && !parts.employer) {
    // The PDF draws such a heading as a single bold line.
    return { kind: "entry", role: plain(line), employer: "", location: "", dates: "" };
  }
  return {
    kind: "entry",
    role: parts.role,
    employer: parts.employer,
    location: parts.location,
    dates: formatDates(parts.start, parts.end),
  };
}

export function parseResumeMarkdown(md: string): ParsedResume {
  const parsed: ParsedResume = { name: "", headline: [], contact: [], sections: [] };
  const lines = cleanPlaceholders(md ?? "");
  const hasMarkdownSections = lines.some((raw) => HEADING.test(raw.trim()));

  let firstLine = true;
  let inHeader = true;
  let current: ResumeSection | null = null;
  const push = (item: ResumeItem) => {
    if (!current) {
      current = { title: "", items: [] };
      parsed.sections.push(current);
    }
    current.items.push(item);
  };

  for (const raw of lines) {
    let line = raw.trim();
    if (!line || RULE_LINES.has(line)) continue;
    const heading = HEADING.exec(line);
    const level = heading ? heading[1].length : 0;
    if (heading) line = line.slice(heading[0].length).trim();
    if (!line) continue;
    const text = plain(line);

    if (firstLine) {
      parsed.name = text;
      firstLine = false;
      continue;
    }

    const section = text.replace(/:+$/, "");
    const capsHeading =
      !hasMarkdownSections &&
      isUpperCase(section) &&
      section.length > 2 &&
      section.length < 40 &&
      !LIST_SEPARATORS.test(section);
    if (SECTIONS.has(section.toLowerCase()) || (level === 2 && section.length < 50) || capsHeading) {
      inHeader = false;
      current = { title: section.toUpperCase(), items: [] };
      parsed.sections.push(current);
      continue;
    }

    if (inHeader) {
      if (CONTACT_HINT.test(text)) {
        parsed.contact.push(
          ...line
            .split(CONTACT_SPLIT)
            .map((p) => p.trim())
            .filter((p) => p && !isPlaceholder(p)),
        );
        continue;
      }
      if (level === 0 && !BULLET.test(line) && text.length < 90) {
        parsed.headline.push(line);
        continue;
      }
    }
    inHeader = false;

    const bullet = BULLET.exec(line);
    if (bullet) {
      push({ kind: "bullet", text: line.slice(bullet[0].length) });
      continue;
    }
    const isEntry = level >= 3 || (line.startsWith("**") && line.includes("|") && ENTRY_DATE.test(text));
    if (isEntry) {
      push(entryItem(line));
      continue;
    }
    push({ kind: "text", text: line });
  }
  return parsed;
}
