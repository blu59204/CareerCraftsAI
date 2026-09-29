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

export type { ResumeTemplateId } from "@/lib/resume-types";

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
const RANGE_SPLIT = /\s*(?:\s-\s|–|—|\bto\b|-(?=\s*(?:\d|present|current|now|ongoing)))\s*/i;
/** A whole heading/contact part that is only N/A, TBD or NOT_PROVIDED (any case). */
const PLACEHOLDER = /^\W*(?:not[_ ]provided|n\/a|tbd)\W*$/i;
/** A line whose entire content is the NOT_PROVIDED marker. */
const PLACEHOLDER_LINE = /^\W*not[_ ]provided\W*$/i;
/** Inside prose only the model's exact uppercase marker is removed. */
const PLACEHOLDER_INLINE = /[[(]?\bNOT[_ ]PROVIDED\b[\])]?/g;
const MONTH =
  "jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?" +
  "|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?";
const DATE_TOKEN = new RegExp(
  `(?:${MONTH})\\b\\.?` +
    "|(?:spring|summer|fall|autumn|winter|present|current|now|ongoing|to)\\b" +
    "|(?:0?[1-9]|1[0-2])/(?:19|20)\\d{2}\\b" +
    "|(?:19|20)\\d{2}\\b",
  "iy",
);
const DATE_SEP = /[\s,/\-–—]+/y;
const REMOTE_WORDS = new Set(["remote", "hybrid", "on-site", "onsite", "on site", "wfh", "work from home"]);
const CAP_WORDS = "[A-Z][\\p{L}\\p{N}_.'-]*(?:\\s+[A-Z][\\p{L}\\p{N}_.'-]*){0,2}";
const CITY_REGION = new RegExp(`^${CAP_WORDS},\\s*${CAP_WORDS}$`, "u");
const COMPANY_SUFFIX = /\b(?:inc|llc|llp|ltd|limited|pvt|corp|corporation|co|company|gmbh|plc|ag|bv)\b/i;
const CONTACT_HINT = /@|(?:\+?\d[\d\s().-]{7,})|(?:linkedin|github)\.com|https?:\/\//i;
const CONTACT_SPLIT = /\s*[|·•]\s*/;
const LIST_SEPARATORS = /[,;|/]/;
const RULE_LINES = new Set(["---", "***", "___"]);

function splitLines(value: string): string[] {
  return value.split(/\r\n|\r|\n/);
}

/** Strip Markdown emphasis/code markers; underscores inside words (jane_doe) are kept. */
function plain(value: string): string {
  const v = value.replace(/[*`]/g, "").trim();
  const wrapped = /^_+(.*?)_+$/.exec(v);
  return (wrapped ? wrapped[1] : v).trim();
}

function isPlaceholder(value: string): boolean {
  const v = plain(value);
  return !!v && PLACEHOLDER.test(v);
}

function looksLikeDates(value: string): boolean {
  return YEAR.test(value) || DATE_WORD.test(value);
}

/**
 * True when `text` consists only of date tokens (months, seasons, 19xx/20xx,
 * MM/YYYY, Present/Current/Now/Ongoing, "to") and separators (- – — , /
 * whitespace), with at least one year or Present-style word. Mirrors backend
 * `is_date_range`: "Deloitte (Summer 2023)" and "Mid-2021 - 2023" are not dates.
 */
export function isDateRange(text: string): boolean {
  const value = plain(text ?? "");
  if (!value || !looksLikeDates(value)) return false;
  let pos = 0;
  while (pos < value.length) {
    DATE_SEP.lastIndex = pos;
    let m = DATE_SEP.exec(value);
    if (!m) {
      DATE_TOKEN.lastIndex = pos;
      m = DATE_TOKEN.exec(value);
    }
    if (!m || m[0].length === 0) return false;
    pos += m[0].length;
  }
  return true;
}

function looksLikeLocation(value: string): boolean {
  const v = value.trim();
  if (REMOTE_WORDS.has(v.toLowerCase())) return true;
  return CITY_REGION.test(v) && !COMPANY_SUFFIX.test(v);
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
    let stripped = line.trim();
    const heading = HEADING.exec(stripped);
    if (stripped.includes("|")) {
      // Pipe-separated heading/contact parts: blank placeholder parts. Heading
      // slots stay positional (inner empties kept, trailing ones dropped).
      const body = heading ? stripped.slice(heading[0].length) : stripped;
      const parts = body.split("|").map((p) => p.trim());
      let blanked = parts.map((p) => (isPlaceholder(p) ? "" : p));
      if (blanked.some((p, i) => p !== parts[i])) {
        if (heading || stripped.startsWith("**")) {
          while (blanked.length && !blanked[blanked.length - 1]) blanked.pop();
        } else {
          blanked = blanked.filter(Boolean);
        }
        if (!blanked.some(Boolean)) continue;
        line = (heading ? `${heading[1]} ` : "") + blanked.join(" | ");
        stripped = line.trim();
      }
    }
    const body = stripped.replace(HEADING, "");
    if (body && PLACEHOLDER_LINE.test(plain(body))) continue;
    // Inline "(NOT_PROVIDED)" fragments inside prose (uppercase marker only).
    const replaced = line.replace(PLACEHOLDER_INLINE, "");
    if (replaced !== line) {
      const tidy = replaced
        .trimEnd()
        .replace(/(?<=\S)[ \t]{2,}/g, " ")
        .replace(/[ \t]+([,.;:!?)\]])/g, "$1");
      if (!tidy.trim().replace(/^[#*\-•]+|[#*\-•]+$/g, "").trim()) continue;
      line = tidy;
    }
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
    if (start && end && looksLikeDates(start)) return [start, end];
  }
  return [value.trim(), ""];
}

/**
 * `Role | Employer | Location | Dates` → parts (any part may be absent).
 *
 * Slots are positional when the heading has an empty inner slot
 * (`Engineer |  | Remote | 2021 - 2022`). Otherwise (legacy headings) the last
 * part is dates only if it is a pure date range, and a lone second part that
 * looks like a location (Remote, `City, Country`) is read as the location.
 */
export function splitHeading(text: string): HeadingParts {
  let parts = text.split("|").map((p) => {
    const v = plain(p);
    return isPlaceholder(v) ? "" : v;
  });
  while (parts.length && !parts[parts.length - 1]) parts.pop();
  const positional = parts.includes("");
  let dates = "";
  if (parts.length > 1 && isDateRange(parts[parts.length - 1])) {
    dates = parts.pop() ?? "";
  }
  if (!positional && parts.length === 2 && looksLikeLocation(parts[1])) {
    parts = [parts[0], "", parts[1]];
  }
  const [start, end] = dates ? splitDates(dates) : ["", ""];
  return {
    role: parts[0] ?? "",
    employer: parts[1] ?? "",
    location: parts.slice(2).filter(Boolean).join(", "),
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
//
// A line-for-line port of backend pdf_service `_bold_spans` / `_italic_pieces`
// / `_inline` (contract C4) so the preview segments exactly like the PDF:
//   * `**` markers pair left to right first; unmatched ones stay literal.
//     After a `***` opener the closer is the last two stars of its run, so
//     `***x***` is bold around `*x*`.
//   * `*x*` italics: a lone star that is not word-internal (`C*`, `5*3`,
//     `*args` stay literal) with no whitespace just inside it. Italics pair
//     inside one bold span or around whole bold spans, so the result always
//     nests; crossing spans (`**a *b** c*`) keep bold and leave the stars literal.
//   * Each opener finds its closer by binary search, so long lines stay fast.

/** Stands in for a whole bold span while pairing italics. */
const SPAN = "\u0000";
const WORD_CHAR = /^[\p{L}\p{N}_]$/u;

/** Python `ch.isalnum() or ch == "_"` for one (possibly astral) character. */
function isWord(ch: string): boolean {
  return ch !== "" && WORD_CHAR.test(ch);
}

function isSpace(ch: string): boolean {
  return ch !== "" && /^\s$/u.test(ch);
}

/** The code point just before / after UTF-16 index `k` (Python indexes code points). */
function charBefore(text: string, k: number): string {
  if (k <= 0) return "";
  const low = text.charCodeAt(k - 1);
  if (low >= 0xdc00 && low <= 0xdfff && k >= 2) {
    const high = text.charCodeAt(k - 2);
    if (high >= 0xd800 && high <= 0xdbff) return text.slice(k - 2, k);
  }
  return text[k - 1];
}

function charAfter(text: string, k: number): string {
  if (k + 1 >= text.length) return "";
  return String.fromCodePoint(text.codePointAt(k + 1) ?? 0);
}

function boldSpans(text: string): Array<[number, number]> {
  const spans: Array<[number, number]> = [];
  let i = 0;
  let start: number;
  while ((start = text.indexOf("**", i)) !== -1) {
    const triple = text.startsWith("*", start + 2);
    let end = text.indexOf("**", start + 3);
    while (end !== -1 && triple && text.startsWith("*", end + 2)) end = text.indexOf("**", end + 1);
    if (end === -1) {
      i = start + 2;
      continue;
    }
    spans.push([start, end]);
    i = end + 2;
  }
  return spans;
}

function italicPieces(text: string): Array<[string, boolean]> {
  const opens = (k: number) => {
    const prev = charBefore(text, k);
    const next = charAfter(text, k);
    return !!next && !isSpace(next) && prev !== "*" && next !== "*" && !isWord(prev);
  };
  const closes = (k: number) => {
    const prev = charBefore(text, k);
    const next = charAfter(text, k);
    return !!prev && !isSpace(prev) && prev !== "*" && next !== "*" && !isWord(next);
  };
  const stars: number[] = [];
  for (let k = 0; k < text.length; k++) if (text[k] === "*") stars.push(k);
  const closers = stars.filter(closes);
  const pieces: Array<[string, boolean]> = [];
  let last = 0;
  for (const k of stars) {
    if (k < last || !opens(k)) continue;
    // bisect_left(closers, k + 2)
    let lo = 0;
    let hi = closers.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (closers[mid] < k + 2) lo = mid + 1;
      else hi = mid;
    }
    if (lo === closers.length) continue;
    const close = closers[lo];
    if (k > last) pieces.push([text.slice(last, k), false]);
    pieces.push([text.slice(k + 1, close), true]);
    last = close + 1;
  }
  if (last < text.length) pieces.push([text.slice(last), false]);
  return pieces;
}

/**
 * Split text with **bold** and *italic* into plain tokens for safe rendering
 * (no HTML is produced). Links become "label (url)"; backticks are dropped.
 */
export function tokenizeInline(value: string): InlineToken[] {
  const text = value
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1 ($2)")
    .replace(/`/g, "")
    .split(SPAN)
    .join("");
  const bolds: string[] = [];
  let top = "";
  let last = 0;
  for (const [start, end] of boldSpans(text)) {
    top += text.slice(last, start) + SPAN;
    bolds.push(text.slice(start + 2, end));
    last = end + 2;
  }
  top += text.slice(last);

  const tokens: InlineToken[] = [];
  const push = (chunk: string, bold: boolean, italic: boolean) => {
    if (!chunk) return;
    const prev = tokens[tokens.length - 1];
    if (prev && prev.bold === bold && prev.italic === italic) prev.text += chunk;
    else tokens.push({ text: chunk, bold, italic });
  };
  let nextBold = 0;
  for (const [piece, italic] of italicPieces(top)) {
    piece.split(SPAN).forEach((chunk, k) => {
      if (k) {
        for (const [inner, innerItalic] of italicPieces(bolds[nextBold++] ?? "")) {
          push(inner, true, italic || innerItalic);
        }
      }
      push(chunk, false, italic);
    });
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
