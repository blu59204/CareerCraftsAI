"use client";

import { memo, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import {
  parseResumeMarkdown,
  tokenizeInline,
  type ResumeItem,
  type ResumeTemplateId,
} from "@/lib/resume-markdown";

/**
 * HTML preview of a tailored resume that mirrors the three ReportLab
 * templates in backend/app/services/pdf_service.py (fonts, sizes, colors,
 * margins, two-row entries). Sizes are expressed in PDF points relative to
 * the paper width (612pt = 8.5in) via container query units, so the page
 * keeps true proportions at any rendered width.
 */

type Theme = {
  font: string;
  ink: string; // name + headings + rules
  text: string; // body
  muted: string; // contact, dates, location
  align: "center" | "left";
  nameSize: number;
  headingSize: number;
  bodySize: number;
  leading: number;
  marginX: number; // inches
  marginY: number; // inches
  sectionGap: number; // pt
  rule: number; // pt
};

const SANS = "Helvetica, Arial, 'Liberation Sans', sans-serif";
const SERIF = "'Times New Roman', Times, 'Liberation Serif', serif";

const THEMES: Record<ResumeTemplateId, Theme> = {
  modern: {
    font: SANS, ink: "#1F3A5F", text: "#1A1A1A", muted: "#4A5563", align: "center",
    nameSize: 22, headingSize: 11, bodySize: 10, leading: 1.32,
    marginX: 0.65, marginY: 0.55, sectionGap: 10, rule: 0.8,
  },
  classic: {
    font: SERIF, ink: "#000000", text: "#000000", muted: "#222222", align: "center",
    nameSize: 20, headingSize: 11.5, bodySize: 10.8, leading: 1.25,
    marginX: 0.75, marginY: 0.6, sectionGap: 9, rule: 0.6,
  },
  technical: {
    font: SANS, ink: "#0F5C63", text: "#1A1A1A", muted: "#46525A", align: "left",
    nameSize: 19, headingSize: 10.5, bodySize: 9.6, leading: 1.28,
    marginX: 0.55, marginY: 0.5, sectionGap: 8, rule: 0.6,
  },
};

/** Letter page at 96 CSS px per inch. */
const PAGE_WIDTH_PX = 816;
const PAGE_HEIGHT_PX = 1056;
const PAGE_WIDTH_PT = 612;

/** PDF points → a length proportional to the paper width. */
function pt(value: number): string {
  return `calc(${value} * 100cqw / ${PAGE_WIDTH_PT})`;
}

function Inline({ text }: { text: string }): ReactNode {
  return tokenizeInline(text).map((token, i) => {
    if (!token.bold && !token.italic) return <span key={i}>{token.text}</span>;
    return (
      <span
        key={i}
        style={{
          fontWeight: token.bold ? 700 : undefined,
          fontStyle: token.italic ? "italic" : undefined,
        }}
      >
        {token.text}
      </span>
    );
  });
}

function Row({
  left,
  right,
  leftStyle,
  rightStyle,
  style,
}: {
  left: ReactNode;
  right: ReactNode;
  leftStyle: CSSProperties;
  rightStyle: CSSProperties;
  style?: CSSProperties;
}) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: pt(8), ...style }}>
      <div style={{ flex: "1 1 auto", minWidth: 0, ...leftStyle }}>{left}</div>
      {right ? (
        <div style={{ flex: "0 0 auto", whiteSpace: "nowrap", textAlign: "right", ...rightStyle }}>
          {right}
        </div>
      ) : null}
    </div>
  );
}

function Item({ item, theme }: { item: ResumeItem; theme: Theme }) {
  const body = theme.bodySize;
  const bodyLine = body * theme.leading;

  if (item.kind === "bullet") {
    return (
      <div
        style={{
          position: "relative",
          paddingLeft: pt(12),
          marginBottom: pt(1.2),
          fontSize: pt(body),
          lineHeight: pt(bodyLine),
        }}
      >
        <span aria-hidden="true" style={{ position: "absolute", left: pt(2) }}>
          •
        </span>
        <Inline text={item.text} />
      </div>
    );
  }

  if (item.kind === "text") {
    return (
      <p style={{ margin: 0, marginBottom: pt(2), fontSize: pt(body), lineHeight: pt(bodyLine) }}>
        <Inline text={item.text} />
      </p>
    );
  }

  const roleSize = body + 0.4;
  const rightSize = body - 0.4;
  const top = item.role || item.employer;
  const employer = item.role ? item.employer : "";
  return (
    <div style={{ marginTop: pt(5), marginBottom: pt(1.5) }}>
      <Row
        left={<Inline text={top} />}
        right={item.dates}
        leftStyle={{ fontWeight: 700, fontSize: pt(roleSize), lineHeight: pt(roleSize * 1.3) }}
        rightStyle={{ color: theme.muted, fontSize: pt(rightSize), lineHeight: pt(roleSize * 1.3) }}
      />
      {employer || item.location ? (
        <Row
          left={employer ? <Inline text={employer} /> : null}
          right={item.location}
          leftStyle={{ fontStyle: "italic", fontSize: pt(body), lineHeight: pt(bodyLine) }}
          rightStyle={{
            fontStyle: "italic",
            color: theme.muted,
            fontSize: pt(rightSize),
            lineHeight: pt(bodyLine),
          }}
        />
      ) : null}
    </div>
  );
}

/**
 * Dashed markers where the continuous HTML page would break onto a new PDF
 * page. Each PDF page holds (11in − top − bottom margin) of content, and the
 * HTML page shows the top margin once and the bottom margin once, so page N+1
 * starts at topMargin + N × contentHeight. Approximate: ReportLab moves whole
 * flowables to the next page, so real breaks can come slightly earlier.
 */
function PageBreaks({ height, width, marginY }: { height: number; width: number; marginY: number }) {
  if (!width || !height) return null;
  const inch = width / 8.5;
  const margin = marginY * inch;
  const pageContent = (11 - 2 * marginY) * inch;
  const content = height - 2 * margin;
  const count = Math.max(0, Math.ceil(content / pageContent - 0.001) - 1);
  if (!count) return null;
  return (
    <div aria-hidden="true" style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
      {Array.from({ length: count }, (_, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: margin + pageContent * (i + 1),
            borderTop: "1px dashed #94A3B8",
          }}
        >
          <span
            style={{
              position: "absolute",
              right: 6,
              top: 2,
              padding: "0 6px",
              borderRadius: 999,
              background: "#F1F5F9",
              color: "#475569",
              fontFamily: SANS,
              fontSize: 10,
              lineHeight: "16px",
            }}
          >
            Page {i + 2}
          </span>
        </div>
      ))}
    </div>
  );
}

export interface ResumePreviewProps {
  markdown: string;
  template: ResumeTemplateId;
  className?: string;
  /** Thumbnail scale: lays out at full letter width, then transforms. */
  scale?: number;
  /** The name the PDF prints; when non-empty it replaces the parsed `# Name`. */
  displayName?: string;
  /** Overlay a dashed marker where the PDF would start a new page (main preview). */
  showPageBreaks?: boolean;
  /** Zoom factor for the fit-to-width preview (1 = fit, capped at letter width). */
  zoom?: number;
  /** Minimum paper width in px at zoom 1 (the container scrolls horizontally). */
  minWidth?: number;
}

function ResumePreviewImpl({
  markdown,
  template,
  className,
  scale = 1,
  displayName,
  showPageBreaks = false,
  zoom = 1,
  minWidth,
}: ResumePreviewProps) {
  const theme = THEMES[template] ?? THEMES.modern;
  const resume = useMemo(() => parseResumeMarkdown(markdown), [markdown]);
  const name = displayName?.trim() || resume.name;
  const scaled = scale > 0 && scale !== 1;
  const isEmpty = !name && !resume.sections.length && !resume.contact.length;

  const articleRef = useRef<HTMLElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const el = articleRef.current;
    if (!showPageBreaks || !el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      const width = el.offsetWidth;
      const height = el.offsetHeight;
      setSize((prev) => (prev.width === width && prev.height === height ? prev : { width, height }));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [showPageBreaks]);

  // Scaled thumbnails: the outer box takes the scaled page size (clipping to
  // page one) while the inner box lays out at full letter width.
  const outerStyle: CSSProperties = scaled
    ? {
        width: PAGE_WIDTH_PX * scale,
        height: PAGE_HEIGHT_PX * scale,
        overflow: "hidden",
        flex: "0 0 auto",
      }
    : {
        width: `${zoom * 100}%`,
        maxWidth: PAGE_WIDTH_PX * zoom,
        minWidth: minWidth ? minWidth * zoom : undefined,
      };
  const containerStyle: CSSProperties = {
    containerType: "inline-size",
    position: "relative",
    width: scaled ? PAGE_WIDTH_PX : "100%",
    transform: scaled ? `scale(${scale})` : undefined,
    transformOrigin: "top left",
  };

  return (
    <div className={className} style={outerStyle}>
      <div style={containerStyle}>
        <article
          ref={articleRef}
          role="document"
          aria-label="Resume preview"
          className="text-left"
          style={{
            colorScheme: "light",
            boxSizing: "border-box",
            width: "100%",
            aspectRatio: "8.5 / 11",
            background: "#FFFFFF",
            color: theme.text,
            fontFamily: theme.font,
            fontSize: pt(theme.bodySize),
            lineHeight: pt(theme.bodySize * theme.leading),
            padding: `${pt(theme.marginY * 72)} ${pt(theme.marginX * 72)}`,
            boxShadow: "0 1px 3px rgba(15, 23, 42, 0.12), 0 8px 24px rgba(15, 23, 42, 0.08)",
            overflowWrap: "anywhere",
          }}
        >
          {isEmpty ? (
            <p style={{ margin: 0, color: "#6B7280", textAlign: "center", paddingTop: pt(120) }}>
              Nothing to preview yet.
            </p>
          ) : null}

          {name || resume.headline.length || resume.contact.length ? (
            <header style={{ textAlign: theme.align }}>
              {name ? (
                // Not an <h1>: the preview sits under the page's "Preview" heading.
                <p
                  role="heading"
                  aria-level={3}
                  style={{
                    margin: 0,
                    marginBottom: pt(3),
                    color: theme.ink,
                    fontWeight: 700,
                    fontSize: pt(theme.nameSize),
                    lineHeight: pt(theme.nameSize * 1.15),
                  }}
                >
                  <Inline text={name} />
                </p>
              ) : null}
              {resume.headline.map((line, i) => (
                <p
                  key={i}
                  style={{
                    margin: 0,
                    marginBottom: pt(1),
                    fontSize: pt(theme.bodySize + 1),
                    lineHeight: pt((theme.bodySize + 1) * 1.3),
                  }}
                >
                  <Inline text={line} />
                </p>
              ))}
              {resume.contact.length ? (
                <p
                  style={{
                    margin: 0,
                    marginBottom: pt(1),
                    color: theme.muted,
                    fontSize: pt(theme.bodySize - 0.6),
                    lineHeight: pt(theme.bodySize * 1.35),
                  }}
                >
                  {resume.contact.map((part, i) => (
                    <span key={i}>
                      {i > 0 ? " | " : null}
                      <Inline text={part} />
                    </span>
                  ))}
                </p>
              ) : null}
            </header>
          ) : null}

          {resume.sections.map((section, s) => (
            // A plain div: named <section>s would add a landmark per resume section.
            <div key={s}>
              {section.title ? (
                <p
                  role="heading"
                  aria-level={4}
                  style={{
                    margin: 0,
                    marginTop: pt(theme.sectionGap),
                    paddingBottom: pt(2),
                    marginBottom: pt(4),
                    borderBottom: `max(1px, ${pt(theme.rule)}) solid ${theme.ink}`,
                    color: theme.ink,
                    fontWeight: 700,
                    fontSize: pt(theme.headingSize),
                    lineHeight: pt(theme.headingSize * 1.25),
                    textTransform: "uppercase",
                    letterSpacing: 0,
                  }}
                >
                  {section.title}
                </p>
              ) : null}
              {section.items.map((item, i) => (
                <Item key={i} item={item} theme={theme} />
              ))}
            </div>
          ))}
        </article>
        {showPageBreaks ? <PageBreaks width={size.width} height={size.height} marginY={theme.marginY} /> : null}
      </div>
    </div>
  );
}

export const ResumePreview = memo(ResumePreviewImpl);
