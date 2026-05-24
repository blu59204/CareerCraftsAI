"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "motion/react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import {
  Mail,
  Send,
  Edit,
  Clock,
  Check,
  AlertCircle,
  ChevronRight,
  Zap,
  MailMinus,
  Archive,
  Tag,
  Inbox,
  ShieldCheck,
  RefreshCw,
} from "lucide-react";

interface Draft {
  id: string;
  subject: string;
  company: string;
  timestamp: string;
  initial: string;
  body: string;
  status?: string;
}

const DRAFTS: Draft[] = [
  {
    id: "1",
    subject: "Following up on Frontend Engineer",
    company: "Acme Corp",
    timestamp: "2h ago",
    initial: "A",
    body: "Hi Sarah,\n\nI wanted to follow up on my application for the Frontend Engineer position at Acme Corp. I submitted my application last week and am very excited about the opportunity to join your team.\n\nI'd love to schedule a quick call to discuss how my experience with React and TypeScript aligns with your needs.\n\nLooking forward to hearing from you.\n\nBest regards,\nAlex",
  },
  {
    id: "2",
    subject: "Intro to Delta Tech",
    company: "Delta Tech",
    timestamp: "Yesterday",
    initial: "D",
    body: "Hi Marcus,\n\nI came across Delta Tech's work on distributed systems and was impressed by your recent engineering blog post. I'm a full-stack developer with 4 years of experience and I believe I could contribute meaningfully to your backend team.\n\nWould you be open to a brief conversation?\n\nBest,\nAlex",
  },
  {
    id: "3",
    subject: "Re: Interview scheduling",
    company: "BetaCorp",
    timestamp: "2d ago",
    initial: "B",
    body: "Hi Jamie,\n\nThank you for getting back to me! I'm available for an interview on Thursday between 10am–2pm or Friday morning. Please let me know which time works best for your team.\n\nLooking forward to it!\n\nBest,\nAlex",
  },
  {
    id: "4",
    subject: "Cold outreach - Backend role",
    company: "Gamma",
    timestamp: "3d ago",
    initial: "G",
    body: "Hi Team,\n\nI noticed Gamma is hiring backend engineers and your microservices architecture really caught my attention. I have deep experience with Python, FastAPI, and distributed systems.\n\nI'd love to connect and learn more about the role.\n\nBest regards,\nAlex",
  },
];

const SUGGESTIONS = [
  {
    id: "1",
    title: "Personalize subject line",
    description: "Mention the specific role and company initiative",
  },
  {
    id: "2",
    title: "Add social proof",
    description: "Reference a recent project or achievement",
  },
  {
    id: "3",
    title: "CTA optimization",
    description: "Use a specific date/time for the interview request",
  },
];

const FOLLOW_UP_STEPS = [
  { day: "Day 1", label: "Initial outreach", status: "done" as const },
  { day: "Day 3", label: "Follow-up", status: "pending" as const },
  { day: "Day 7", label: "Final nudge", status: "upcoming" as const },
];

interface Template {
  id: string;
  name: string;
  body: string;
}

const TEMPLATES: Template[] = [
  {
    id: "t1",
    name: "Referral ask",
    body: "Hi [Name], I noticed you work at [Company] and I'm applying for [Role]. Would you be open to a 15-minute chat about the team culture?",
  },
  {
    id: "t2",
    name: "Direct recruiter outreach",
    body: "Hi [Name], I came across your profile and wanted to reach out about opportunities at [Company]. My background in [Skill] aligns well with what you're hiring for.",
  },
  {
    id: "t3",
    name: "Warm intro follow-up",
    body: "Following up on my application for [Role] at [Company]. I wanted to share how my work on [Project] directly maps to your needs.",
  },
  {
    id: "t4",
    name: "Coffee chat",
    body: "Hi [Name], I've been following [Company]'s work on [Product] and I'm genuinely excited about what you're building. Would you be open to a quick 20-minute chat?",
  },
  {
    id: "t5",
    name: "Post-rejection keep-warm",
    body: "Thank you for the update. I'd love to stay in touch for future opportunities that might be a better fit.",
  },
];

function TemplateCard({
  template,
  onUse,
}: {
  template: Template;
  onUse: (body: string) => void;
}) {
  const preview =
    template.body.length > 80 ? template.body.slice(0, 80) + "…" : template.body;

  return (
    <div className="rounded-2xl border border-border bg-background/50 p-3 space-y-2">
      <p className="text-xs font-semibold text-foreground">{template.name}</p>
      <p className="text-xs leading-relaxed text-muted-foreground">{preview}</p>
      <button
        onClick={() => onUse(template.body)}
        className="flex items-center gap-1 rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:bg-card/70"
      >
        Use template
      </button>
    </div>
  );
}

function DraftCard({
  draft,
  active,
  onClick,
}: {
  draft: Draft;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full rounded-2xl border p-3 text-left transition-all",
        active
          ? "border-primary/30 bg-primary/10"
          : "border-border bg-card/40 hover:bg-card/70"
      )}
    >
      <div className="flex items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-semibold text-primary">
          {draft.initial}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground">
            {draft.subject}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {draft.company} &middot; {draft.timestamp}
          </p>
        </div>
      </div>
    </button>
  );
}

function FollowUpStep({
  day,
  label,
  status,
}: {
  day: string;
  label: string;
  status: "done" | "pending" | "upcoming";
}) {
  return (
    <div className="flex items-center gap-3">
      <div
        className={cn(
          "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs",
          status === "done" && "bg-green-100 text-green-600",
          status === "pending" && "bg-amber-100 text-amber-600",
          status === "upcoming" && "bg-muted text-muted-foreground"
        )}
      >
        {status === "done" && <Check className="h-3 w-3" />}
        {status === "pending" && <Clock className="h-3 w-3" />}
        {status === "upcoming" && (
          <span className="h-2 w-2 rounded-full bg-muted-foreground/40" />
        )}
      </div>
      <div className="flex-1">
        <span className="text-xs font-medium text-foreground">{day}</span>
        <span className="ml-2 text-xs text-muted-foreground">{label}</span>
      </div>
      {status === "done" && (
        <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
          Sent
        </span>
      )}
      {status === "pending" && (
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
          Queued
        </span>
      )}
    </div>
  );
}

type InboxCategory = "important" | "newsletter" | "promo" | "social";

interface InboxEmail {
  id: string;
  from: string;
  subject: string;
  preview: string;
  category: InboxCategory;
  date: string;
  unsubscribable: boolean;
}

const INBOX_EMAILS: InboxEmail[] = [
  { id: "i1", from: "LinkedIn", subject: "12 new jobs match your preferences", preview: "Remote React roles at top companies", category: "newsletter", date: "Today", unsubscribable: true },
  { id: "i2", from: "AWS", subject: "Your account: promotional credits available", preview: "$100 in free credits expire soon", category: "promo", date: "Today", unsubscribable: true },
  { id: "i3", from: "GitHub", subject: "Security alert: new sign-in", preview: "A new device signed into your account", category: "important", date: "Yesterday", unsubscribable: false },
  { id: "i4", from: "Medium Daily", subject: "Top stories: AI coding tools 2026", preview: "What engineers are saying about…", category: "newsletter", date: "Yesterday", unsubscribable: true },
  { id: "i5", from: "Stripe", subject: "Your invoice for May 2026", preview: "Invoice #INV-2026-001 is ready", category: "important", date: "2d ago", unsubscribable: false },
  { id: "i6", from: "Glassdoor", subject: "Don't miss these company reviews", preview: "New reviews for companies you follow", category: "newsletter", date: "3d ago", unsubscribable: true },
  { id: "i7", from: "Shopify", subject: "Flash sale — 40% off this weekend", preview: "Limited-time offer on premium themes", category: "promo", date: "3d ago", unsubscribable: true },
  { id: "i8", from: "Twitter/X", subject: "You have new notifications", preview: "3 people mentioned you this week", category: "social", date: "4d ago", unsubscribable: true },
];

const CATEGORY_COLORS: Record<InboxCategory, string> = {
  important: "bg-blue-100 text-blue-700",
  newsletter: "bg-purple-100 text-purple-700",
  promo: "bg-orange-100 text-orange-700",
  social: "bg-green-100 text-green-700",
};

function InboxCleanup() {
  const [emails, setEmails] = useState(INBOX_EMAILS);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<InboxCategory | "all">("all");
  const [cleaning, setCleaning] = useState(false);

  const visible = filter === "all" ? emails : emails.filter((e) => e.category === filter);
  const unsubCount = emails.filter((e) => e.unsubscribable).length;

  const toggle = (id: string) =>
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const archiveSelected = () => {
    setEmails((prev) => prev.filter((e) => !selectedIds.has(e.id)));
    setSelectedIds(new Set());
  };

  const unsubAll = () => {
    setCleaning(true);
    setTimeout(() => {
      setEmails((prev) => prev.filter((e) => !e.unsubscribable));
      setCleaning(false);
    }, 1200);
  };

  const stats = {
    total: emails.length,
    newsletters: emails.filter((e) => e.category === "newsletter").length,
    promos: emails.filter((e) => e.category === "promo").length,
  };

  return (
    <div className="space-y-4">
      {/* Health stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Total", value: stats.total, icon: Inbox },
          { label: "Newsletters", value: stats.newsletters, icon: MailMinus },
          { label: "Promos", value: stats.promos, icon: Tag },
        ].map(({ label, value, icon: Icon }) => (
          <div key={label} className="rounded-2xl border border-border bg-background/50 p-3 text-center">
            <Icon className="mx-auto mb-1 h-4 w-4 text-muted-foreground" />
            <div className="text-lg font-semibold text-foreground">{value}</div>
            <div className="text-xs text-muted-foreground">{label}</div>
          </div>
        ))}
      </div>

      {/* Bulk action bar */}
      <div className="flex flex-wrap gap-2">
        <LiquidGlassButton
          tone="ghost"
          size="sm"
          onClick={unsubAll}
          disabled={cleaning || unsubCount === 0}
        >
          {cleaning ? (
            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <ShieldCheck className="h-3.5 w-3.5" />
          )}
          Unsubscribe all ({unsubCount})
        </LiquidGlassButton>
        {selectedIds.size > 0 && (
          <LiquidGlassButton tone="ghost" size="sm" onClick={archiveSelected}>
            <Archive className="h-3.5 w-3.5" />
            Archive ({selectedIds.size})
          </LiquidGlassButton>
        )}
      </div>

      {/* Category filter */}
      <div className="flex gap-1 flex-wrap">
        {(["all", "important", "newsletter", "promo", "social"] as const).map((c) => (
          <button
            key={c}
            onClick={() => setFilter(c)}
            className={cn(
              "rounded-full px-2.5 py-1 text-xs capitalize transition-colors",
              filter === c
                ? "bg-primary/10 text-primary font-medium"
                : "text-muted-foreground hover:bg-card"
            )}
          >
            {c}
          </button>
        ))}
      </div>

      {/* Email list */}
      <div className="space-y-2">
        <AnimatePresence initial={false}>
          {visible.map((email) => (
            <motion.div
              key={email.id}
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
            >
              <div
                className={cn(
                  "flex items-start gap-3 rounded-2xl border p-3 transition-all",
                  selectedIds.has(email.id)
                    ? "border-primary/30 bg-primary/5"
                    : "border-border bg-card/40"
                )}
              >
                <input
                  type="checkbox"
                  checked={selectedIds.has(email.id)}
                  onChange={() => toggle(email.id)}
                  className="mt-0.5 h-4 w-4 rounded accent-primary"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-foreground truncate">{email.from}</span>
                    <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-xs font-medium", CATEGORY_COLORS[email.category])}>
                      {email.category}
                    </span>
                  </div>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">{email.subject}</p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <span className="text-xs text-muted-foreground">{email.date}</span>
                  {email.unsubscribable && (
                    <button
                      onClick={() => setEmails((prev) => prev.filter((e) => e.id !== email.id))}
                      className="rounded-full p-1 text-muted-foreground transition-colors hover:bg-red-50 hover:text-red-500"
                      title="Unsubscribe"
                    >
                      <MailMinus className="h-3.5 w-3.5" />
                    </button>
                  )}
                  <button
                    onClick={() => setEmails((prev) => prev.filter((e) => e.id !== email.id))}
                    className="rounded-full p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    title="Archive"
                  >
                    <Archive className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {visible.length === 0 && (
          <div className="rounded-2xl border border-border bg-card/40 p-6 text-center text-sm text-muted-foreground">
            Inbox clean! Nothing to show.
          </div>
        )}
      </div>
    </div>
  );
}

export default function EmailPage() {
  const [selectedId, setSelectedId] = useState<string>("1");
  const [composeText, setComposeText] = useState<string>("");
  const [emailTab, setEmailTab] = useState<"drafts" | "templates" | "inbox">("drafts");

  const { data: drafts = DRAFTS } = useQuery<Draft[]>({
    queryKey: ["email-drafts"],
    queryFn: async () => {
      const { data } = await apiClient.get("/email/drafts");
      return data;
    },
  });

  const selected = drafts.find((d) => d.id === selectedId) ?? drafts[0];

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={stagger}
      className="space-y-8"
    >
      {/* Header */}
      <motion.div
        variants={fadeUp}
        className="flex items-start justify-between"
      >
        <div>
          <div className="text-sm text-muted-foreground">Email Agent</div>
          <h1 className="mt-1 text-3xl font-medium">AI-powered outreach.</h1>
        </div>
        <div className="flex gap-2">
          <LiquidGlassButton tone="primary" size="sm">
            <Mail className="h-4 w-4" />
            Connect Gmail
          </LiquidGlassButton>
          <LiquidGlassButton tone="ghost" size="sm">
            <Edit className="h-4 w-4" />
            New draft
          </LiquidGlassButton>
        </div>
      </motion.div>

      {/* 3-column layout */}
      <motion.div variants={fadeUp} className="flex gap-4">
        {/* Left sidebar */}
        <div className="w-[280px] shrink-0 space-y-4">
          {/* Gmail status */}
          <div className="rounded-3xl border border-border bg-card/60 p-4">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-green-500" />
              <span className="text-sm font-medium text-foreground">
                Gmail Connected
              </span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              alex@gmail.com · Synced 5 min ago
            </p>
          </div>

          {/* Drafts / Templates / Inbox tab list */}
          <div className="rounded-3xl border border-border bg-card/60 p-4">
            {/* Tab switcher */}
            <div className="mb-3 flex gap-1 rounded-full border border-border bg-muted/40 p-1 text-xs">
              {(["drafts", "templates", "inbox"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setEmailTab(t)}
                  className={`flex-1 rounded-full py-1 capitalize transition-colors ${
                    emailTab === t
                      ? "bg-background shadow-sm text-foreground"
                      : "text-muted-foreground"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>

            {emailTab === "drafts" ? (
              <>
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-sm font-medium text-foreground">Drafts</span>
                  <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                    {drafts.length}
                  </span>
                </div>
                <div className="space-y-2">
                  {drafts.map((draft) => (
                    <DraftCard
                      key={draft.id}
                      draft={draft}
                      active={draft.id === selectedId}
                      onClick={() => setSelectedId(draft.id)}
                    />
                  ))}
                </div>
              </>
            ) : emailTab === "templates" ? (
              <>
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-sm font-medium text-foreground">Templates</span>
                  <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                    {TEMPLATES.length}
                  </span>
                </div>
                <div className="space-y-2">
                  {TEMPLATES.map((tpl) => (
                    <TemplateCard
                      key={tpl.id}
                      template={tpl}
                      onUse={(body) => {
                        setComposeText(body);
                        setEmailTab("drafts");
                      }}
                    />
                  ))}
                </div>
              </>
            ) : (
              <InboxCleanup />
            )}
          </div>
        </div>

        {/* Main content */}
        <div className="min-w-0 flex-1 space-y-4">
          {/* Email preview */}
          <div className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-foreground">
                  {selected.subject}
                </h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  To: recruiter@{selected.company.toLowerCase().replace(" ", "")}.com
                </p>
              </div>
              <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-700">
                Draft
              </span>
            </div>
            <div className="rounded-2xl bg-background/60 p-4">
              <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground">
                {selected.body}
              </pre>
            </div>
          </div>

          {/* Compose area */}
          <div className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-medium text-foreground">
                Edit draft
              </span>
              <button className="flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary/20">
                <Zap className="h-3 w-3" />
                AI Draft
              </button>
            </div>
            <textarea
              value={composeText}
              onChange={(e) => setComposeText(e.target.value)}
              placeholder="Edit or compose your email here…"
              rows={5}
              className="w-full resize-none rounded-2xl border border-border bg-background/60 px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            <div className="mt-3 flex gap-2">
              <LiquidGlassButton tone="primary" size="sm">
                <Send className="h-4 w-4" />
                Send
              </LiquidGlassButton>
              <LiquidGlassButton tone="ghost" size="sm">
                Save draft
              </LiquidGlassButton>
            </div>
          </div>
        </div>

        {/* Right sidebar */}
        <div className="w-[280px] shrink-0 space-y-4">
          {/* AI Suggestions */}
          <div className="rounded-3xl border border-border bg-card/60 p-4">
            <div className="mb-3 flex items-center gap-2">
              <span className="text-sm font-semibold text-foreground">
                AI Suggestions
              </span>
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                3
              </span>
            </div>
            <div className="space-y-3">
              {SUGGESTIONS.map((s) => (
                <div
                  key={s.id}
                  className="rounded-2xl border border-border bg-background/50 p-3"
                >
                  <p className="text-xs font-semibold text-foreground">
                    {s.title}
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                    {s.description}
                  </p>
                  <button className="mt-2 flex items-center gap-1 text-xs font-medium text-primary hover:underline">
                    Apply <ChevronRight className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Follow-up schedule */}
          <div className="rounded-3xl border border-border bg-card/60 p-4">
            <p className="mb-3 text-sm font-semibold text-foreground">
              Follow-up Schedule
            </p>
            <div className="space-y-3">
              {FOLLOW_UP_STEPS.map((step) => (
                <FollowUpStep key={step.day} {...step} />
              ))}
            </div>
          </div>
        </div>
      </motion.div>

      {/* Human-in-the-loop warning */}
      <motion.div variants={fadeUp}>
        <div className="flex items-center gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4">
          <AlertCircle className="h-4 w-4 shrink-0 text-amber-600" />
          <p className="text-sm text-amber-800">
            Every email needs your approval before sending.
          </p>
        </div>
      </motion.div>
    </motion.div>
  );
}
