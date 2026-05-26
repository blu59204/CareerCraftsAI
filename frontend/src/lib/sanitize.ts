/**
 * Sanitize LLM-generated content before rendering in the DOM.
 * Uses DOMPurify to strip XSS vectors (script tags, event handlers, javascript: URIs).
 *
 * Security finding FE-002: LLM output rendering XSS risk.
 */

import DOMPurify from "dompurify";

/**
 * Sanitize HTML content from LLM output.
 * Strips: script tags, event handlers (onclick, onerror, etc.), javascript: URIs.
 */
export function sanitizeLLMOutput(html: string): string {
  if (typeof window === "undefined") {
    // SSR: strip all HTML tags as a safe fallback
    return html.replace(/<[^>]*>/g, "");
  }
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ["p", "br", "strong", "em", "ul", "ol", "li", "h1", "h2", "h3", "h4", "code", "pre", "blockquote", "a", "span"],
    ALLOWED_ATTR: ["href", "class"],
    FORBID_ATTR: ["style", "onclick", "onerror", "onload"],
    ALLOW_DATA_ATTR: false,
  });
}

/**
 * Sanitize plain text — escape any HTML entities.
 */
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
