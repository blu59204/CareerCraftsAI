"use client";

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "motion/react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { CommandHeader } from "@/components/immersive/CommandHeader";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import { connectGmail } from "@/lib/nango-connect";
import { toast } from "sonner";
import {
  Mail,
  Send,
  Edit,
  Clock,
  Check,
  AlertCircle,
  ChevronRight,
  Zap,
  Archive,
  Inbox,
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
  recipient_email?: string | null;
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
    applied: "Subject: Following up on [Role] at [Company] — excited about [initiative]",
  },
  {
    id: "2",
    title: "Add social proof",
    description: "Reference a recent project or achievement",
    applied: "\n\nP.S. — I recently shipped [project] which reduced latency by 40%. Happy to share details.",
  },
  {
    id: "3",
    title: "CTA optimization",
    description: "Use a specific date/time for the interview request",
    applied: "\n\nAre you available for a 20-minute call this Thursday between 2–4pm, or Friday morning?",
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
          status === "done" && "bg-success/10 text-success",
          status === "pending" && "bg-warning/10 text-warning",
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
        <span className="rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success">
          Sent
        </span>
      )}
      {status === "pending" && (
        <span className="rounded-full bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning">
          Queued
        </span>
      )}
    </div>
  );
}

interface InboxCleanupEmail {
  id: string;
  from: string;
  subject: string;
  date: string;
  unsubscribe_url: string | null;
}

function InboxCleanup() {
  const qc = useQueryClient();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [archiving, setArchiving] = useState(false);

  const {
    data: emails = [],
    isLoading,
    isError,
  } = useQuery<InboxCleanupEmail[]>({
    queryKey: ["inbox-cleanup"],
    queryFn: async () => (await apiClient.get("/email/inbox-cleanup")).data,
  });

  const toggle = (id: string) =>
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });

  const archiveSelected = async () => {
    if (selectedIds.size === 0) return;
    setArchiving(true);
    try {
      const { data } = await apiClient.post<{ archived: number }>("/email/inbox-cleanup/archive", {
        message_ids: Array.from(selectedIds),
      });
      setSelectedIds(new Set());
      qc.invalidateQueries({ queryKey: ["inbox-cleanup"] });
      toast.success(`${data.archived} emails archived`);
    } catch {
      toast.error("Failed to archive selected emails");
    } finally {
      setArchiving(false);
    }
  };

  const stats = { total: emails.length };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3">
        <div className="rounded-2xl border border-border bg-background/50 p-3 text-center">
          <Inbox className="mx-auto mb-1 h-4 w-4 text-muted-foreground" />
          <div className="text-lg font-semibold text-foreground">{stats.total}</div>
          <div className="text-xs text-muted-foreground">Promotions &amp; updates (30d)</div>
        </div>
      </div>

      {selectedIds.size > 0 && (
        <div className="flex flex-wrap gap-2">
          <LiquidGlassButton tone="ghost" size="sm" onClick={archiveSelected} disabled={archiving}>
            {archiving ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Archive className="h-3.5 w-3.5" />
            )}
            Archive ({selectedIds.size})
          </LiquidGlassButton>
        </div>
      )}

      <div className="space-y-2">
        {isLoading && (
          <div className="rounded-2xl border border-border bg-card/40 p-6 text-center text-sm text-muted-foreground">
            Loading inbox…
          </div>
        )}
        {isError && (
          <div className="flex items-center gap-2 rounded-2xl border border-warning/30 bg-warning/10 px-3 py-2">
            <AlertCircle className="h-3.5 w-3.5 shrink-0 text-warning" />
            <p className="text-xs text-warning">Could not load inbox — connect Gmail in Settings.</p>
          </div>
        )}
        <AnimatePresence initial={false}>
          {emails.map((email) => (
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
                  <span className="text-xs font-semibold text-foreground truncate block">{email.from}</span>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">{email.subject}</p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <span className="text-xs text-muted-foreground">{email.date}</span>
                  {email.unsubscribe_url && (
                    <a
                      href={email.unsubscribe_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded-full px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-danger/10 hover:text-danger"
                      title="Open unsubscribe page"
                    >
                      Open unsubscribe page
                    </a>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {!isLoading && !isError && emails.length === 0 && (
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
  const [recipientEmail, setRecipientEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [emailTab, setEmailTab] = useState<"drafts" | "templates" | "inbox">("drafts");
  const [localDrafts, setLocalDrafts] = useState<Draft[]>(DRAFTS);
  const qc = useQueryClient();

  const { data: remoteDrafts = [] } = useQuery<Draft[]>({
    queryKey: ["email-drafts"],
    queryFn: async () => {
      const { data } = await apiClient.get("/email/drafts");
      return data;
    },
  });

  const { data: connectedAccounts } = useQuery<{ google: boolean; gmail_send: boolean }>({
    queryKey: ["connected-accounts"],
    queryFn: async () => {
      const { data } = await apiClient.get("/users/me/connected-accounts");
      return data;
    },
  });

  const gmailConnectionFlag = connectedAccounts?.gmail_send ?? false;
  const { data: integrations = [] } = useQuery<
    Array<{ provider: string; status: string; account_email: string | null }>
  >({
    queryKey: ["integrations"],
    queryFn: async () => (await apiClient.get("/integrations")).data,
    enabled: gmailConnectionFlag,
  });
  const gmailConnection = integrations.find((connection) => connection.provider === "gmail");
  const gmailConnected = gmailConnectionFlag && gmailConnection?.status === "connected";
  const gmailAccountEmail = gmailConnection?.account_email;

  const drafts = [...localDrafts, ...remoteDrafts.filter((d) => !localDrafts.find((x) => x.id === d.id))];

  const selected = drafts.find((d) => d.id === selectedId) ?? drafts[0];

  useEffect(() => {
    setComposeText(selected?.body ?? "");
    setRecipientEmail(selected?.recipient_email ?? "");
    setSubject(selected?.subject ?? "");
  }, [selected?.body, selected?.recipient_email, selected?.subject, selectedId]);

  const handleSaveDraft = async () => {
    if (!gmailConnected) {
      toast.error("Connect Gmail to save drafts in Gmail.");
      return;
    }
    if (!recipientEmail.trim() || !subject.trim()) {
      toast.info("Add a recipient and subject before saving.");
      return;
    }
    if (!composeText.trim()) {
      toast.info("Nothing to save — compose some text first.");
      return;
    }
    try {
      await apiClient.post("/email/gmail-drafts", {
        recipient_email: recipientEmail,
        subject,
        body: composeText,
      });
      setLocalDrafts((previous) => previous.map((draft) => (
        draft.id === selected?.id
          ? { ...draft, subject, body: composeText, recipient_email: recipientEmail, timestamp: "just now" }
          : draft
      )));
      toast.success("Saved to Gmail drafts");
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail ? `Could not save: ${detail}` : "Failed to save Gmail draft");
    }
  };

  const [sending, setSending] = useState(false);

  const handleSend = async () => {
    if (!gmailConnected) {
      toast.error("Gmail not connected — connect Gmail to send");
      return;
    }
    if (!composeText.trim()) {
      toast.info("Nothing to send — compose some text first.");
      return;
    }
    if (!recipientEmail.trim() || !subject.trim()) {
      toast.info("Add a recipient and subject before sending.");
      return;
    }
    setSending(true);
    try {
      // Clicking Send IS the human-in-the-loop approval: compose creates a
      // pending email (status awaiting_approval), then approve dispatches it.
      const { data: composed } = await apiClient.post<{ run_id: string; status: string }>(
        "/email/compose",
        {
          company: selected?.company ?? "Unknown",
          role: selected?.subject ?? "Draft",
          recipient_email: recipientEmail,
          subject,
          body: composeText,
        },
      );
      if (composed.status !== "awaiting_approval") {
        toast.error("Draft could not be prepared for sending");
        return;
      }
      await apiClient.post(`/email/approve/${composed.run_id}`);
      qc.invalidateQueries({ queryKey: ["email-drafts"] });
      toast.success("Email sent");
      setComposeText("");
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail ? `Send failed: ${detail}` : "Send failed — check Gmail connection");
    } finally {
      setSending(false);
    }
  };

  const handleApplySuggestion = (suggestion: typeof SUGGESTIONS[0]) => {
    setComposeText((prev) => {
      const base = prev || (selected?.body ?? "");
      return base + suggestion.applied;
    });
    toast.success(`Applied: ${suggestion.title}`);
  };

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={stagger}
      className="space-y-8"
    >
      <CommandHeader
        eyebrow="AI Automation"
        title="AI-powered outreach."
        description="Draft follow-ups, personalize messages, and keep human approval before anything gets sent."
        actions={
        <div className="flex flex-wrap gap-2">
          {gmailConnected ? (
            <a href="/settings/integrations">
              <LiquidGlassButton tone="ghost" size="sm">
                <Mail className="h-4 w-4" />
                Manage integrations
              </LiquidGlassButton>
            </a>
          ) : (
            <LiquidGlassButton
              tone="primary"
              size="sm"
              onClick={async () => {
                const { error } = await connectGmail("/email");
                if (error) toast.error(error.message);
              }}
            >
              <Mail className="h-4 w-4" />
              Connect Gmail
            </LiquidGlassButton>
          )}
          <LiquidGlassButton tone="ghost" size="sm" onClick={() => {
            const newId = `new-${Date.now()}`;
            const blank = { id: newId, subject: "New draft", company: "Untitled", timestamp: "just now", initial: "N", body: "", status: "draft" };
            setLocalDrafts((prev) => [blank, ...prev]);
            setSelectedId(newId);
            setComposeText("");
            setEmailTab("drafts");
            toast.success("New draft created");
          }}>
            <Edit className="h-4 w-4" />
            New draft
          </LiquidGlassButton>
        </div>
        }
      />

      {/* 3-column layout */}
      <motion.div variants={fadeUp} className="flex gap-4">
        {/* Left sidebar */}
        <div className="w-[280px] shrink-0 space-y-4">
          <div className="rounded-3xl border border-border bg-card/60 p-4">
            <div className="flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${gmailConnected ? "bg-success" : "bg-muted-foreground"}`} />
              <span className="text-sm font-medium text-foreground">
                {gmailConnected ? "Gmail Connected" : "Gmail Not Connected"}
              </span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {gmailConnected
                ? `${gmailAccountEmail ?? "Connected account"} · Synced`
                : "Connect Gmail in Settings → Account"}
            </p>
          </div>

          <div className="rounded-3xl border border-border bg-card/60 p-4">
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
                        toast.success(`Template "${tpl.name}" loaded`);
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
          {selected ? (
          <div className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-foreground">
                  {subject || selected.subject}
                </h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  To: {recipientEmail || "Add recipient"}
                </p>
              </div>
              <span className="rounded-full bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning">
                Draft
              </span>
            </div>
          </div>
          ) : (
          <div className="rounded-3xl border border-border bg-card/60 p-6 text-center text-sm text-muted-foreground">
            No drafts yet. Compose your first email to get started.
          </div>
          )}

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
            <div className="mb-3 grid gap-3 sm:grid-cols-2">
              <input
                type="email"
                value={recipientEmail}
                onChange={(e) => setRecipientEmail(e.target.value)}
                placeholder="Recipient email"
                className="w-full rounded-2xl border border-border bg-background/60 px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
              <input
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Subject"
                className="w-full rounded-2xl border border-border bg-background/60 px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            <textarea
              value={composeText}
              onChange={(e) => setComposeText(e.target.value)}
              placeholder="Edit or compose your email here…"
              rows={5}
              className="w-full resize-none rounded-2xl border border-border bg-background/60 px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            <div className="mt-3 flex gap-2">
              <LiquidGlassButton tone="primary" size="sm" onClick={handleSend} disabled={sending}>
                <Send className="h-4 w-4" />
                {sending ? "Sending…" : "Send"}
              </LiquidGlassButton>
              <LiquidGlassButton tone="ghost" size="sm" onClick={handleSaveDraft}>
                Save draft
              </LiquidGlassButton>
            </div>
          </div>
        </div>

        {/* Right sidebar */}
        <div className="w-[280px] shrink-0 space-y-4">
          <div className="rounded-3xl border border-border bg-card/60 p-4">
            <div className="mb-3 flex items-center gap-2">
              <span className="text-sm font-semibold text-foreground">
                AI Suggestions
              </span>
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                {SUGGESTIONS.length}
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
                  <button
                    onClick={() => handleApplySuggestion(s)}
                    className="mt-2 flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                  >
                    Apply <ChevronRight className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>

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
        <div className="flex items-center gap-3 rounded-2xl border border-warning/30 bg-warning/10 px-5 py-4">
          <AlertCircle className="h-4 w-4 shrink-0 text-warning" />
          <p className="text-sm text-warning">
            Every email needs your approval before sending.
          </p>
        </div>
      </motion.div>
    </motion.div>
  );
}
