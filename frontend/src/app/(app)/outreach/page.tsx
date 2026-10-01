"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { EnvelopeSimple } from "@phosphor-icons/react";
import { apiClient } from "@/lib/api";
import {
  Bezel,
  EmptyPanel,
  Input,
  IslandButton,
  PageHero,
  PanelTitle,
  Reveal,
  Screen,
  Skeleton,
  StatStrip,
  StatusPill,
  Textarea,
  type StatusTone,
} from "@/components/vanguard";

interface OutreachItem {
  id: string;
  kind: "initial" | "followup";
  company: string;
  role: string | null;
  to_email: string;
  email_source: string | null;
  verdict: "valid" | "risky" | "unknown" | "invalid";
  subject: string;
  body: string;
  state: "held" | "draft" | "approved" | "sending" | "sent" | "failed" | "cancelled";
  resume_version: string | null;
  sent_at: string | null;
  replied_at: string | null;
  bounced_at: string | null;
  opened_at?: string | null;
}

interface OutreachResponse {
  items: OutreachItem[];
  stats: Record<string, number>;
}

function statusOf(item: OutreachItem): { label: string; tone: StatusTone } {
  if (item.bounced_at) return { label: "Bounced", tone: "danger" };
  if (item.replied_at) return { label: "Replied", tone: "success" };
  switch (item.state) {
    case "held":
      return { label: "Address not verified", tone: "warning" };
    case "draft":
      return { label: "Needs your approval", tone: "warning" };
    case "approved":
      return { label: "Queued to send", tone: "primary" };
    case "sending":
      return { label: "Sending", tone: "primary" };
    case "sent":
      return item.opened_at ? { label: "Opened", tone: "primary" } : { label: "Sent", tone: "neutral" };
    case "failed":
      return { label: "Failed", tone: "danger" };
    default:
      return { label: "Cancelled", tone: "neutral" };
  }
}

function Row({ item }: { item: OutreachItem }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState(item.subject);
  const [body, setBody] = useState(item.body);
  const refresh = () => qc.invalidateQueries({ queryKey: ["outreach"] });
  const fail = () => toast.error("That did not work. Refresh and try again.");

  const approve = useMutation({
    mutationFn: () => apiClient.post(`/outreach/${item.id}/approve`),
    onSuccess: refresh,
    onError: fail,
  });
  const cancel = useMutation({
    mutationFn: () => apiClient.post(`/outreach/${item.id}/cancel`),
    onSuccess: refresh,
    onError: fail,
  });
  const save = useMutation({
    mutationFn: () => apiClient.patch(`/outreach/${item.id}`, { subject, body }),
    onSuccess: () => {
      setEditing(false);
      refresh();
    },
    onError: fail,
  });

  const status = statusOf(item);
  const open = item.state === "held" || item.state === "draft";

  return (
    <li className="py-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground">
            {item.company}
            {item.role ? <span className="text-muted-foreground"> · {item.role}</span> : null}
            {item.kind === "followup" ? <span className="text-muted-foreground"> · follow-up</span> : null}
          </p>
          <p className="text-xs text-muted-foreground">
            To {item.to_email}
            {item.email_source ? ` (${item.email_source.replace("_", " ")})` : ""}
            {item.resume_version ? ` · resume ${item.resume_version.slice(0, 8)}` : ""}
          </p>
        </div>
        <StatusPill tone={status.tone}>{status.label}</StatusPill>
      </div>

      {editing ? (
        <div className="mt-3 space-y-2">
          <Input value={subject} onChange={(e) => setSubject(e.target.value)} aria-label="Subject" />
          <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={8} aria-label="Message" />
        </div>
      ) : (
        <div className="mt-3 text-sm leading-6">
          <p className="font-medium text-foreground">{item.subject}</p>
          <p className="mt-1 whitespace-pre-wrap text-muted-foreground">{item.body}</p>
        </div>
      )}

      {item.state === "held" ? (
        <p className="mt-2 text-xs text-muted-foreground">
          We could not confirm this address is real, and a bounce hurts your Gmail reputation. Approve it only if you
          know it is right.
        </p>
      ) : null}

      {open || item.state === "approved" ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {open && !editing ? (
            <IslandButton size="sm" disabled={approve.isPending} onClick={() => approve.mutate()}>
              Approve and send
            </IslandButton>
          ) : null}
          {open && editing ? (
            <IslandButton size="sm" disabled={save.isPending} onClick={() => save.mutate()}>
              Save changes
            </IslandButton>
          ) : null}
          {open ? (
            <IslandButton size="sm" tone="quiet" onClick={() => setEditing((v) => !v)}>
              {editing ? "Discard edits" : "Edit"}
            </IslandButton>
          ) : null}
          <IslandButton size="sm" tone="ghost" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
            Cancel
          </IslandButton>
        </div>
      ) : null}
    </li>
  );
}

export default function OutreachPage() {
  const { data, isLoading } = useQuery<OutreachResponse>({
    queryKey: ["outreach"],
    queryFn: () => apiClient.get("/outreach").then((r) => r.data as OutreachResponse),
    refetchInterval: 60_000,
  });
  const stats = data?.stats ?? {};
  const items = data?.items ?? [];
  const needsYou = items.filter((i) => i.state === "held" || i.state === "draft");
  const rest = items.filter((i) => i.state !== "held" && i.state !== "draft");

  return (
    <Screen>
      <div className="space-y-6 md:space-y-8">
        <PageHero
          className="pb-4 md:pb-6"
          eyebrow="Outreach"
          title="Recruiter emails"
          accent="Verified, personal, and yours to approve."
          description="CareerCraft finds a recruiter's address, checks it is real, and drafts a note with your tailored resume. You approve each one until you choose otherwise."
        />

        <Reveal subtle>
          <StatStrip
            items={[
              { label: "Need you", value: (stats.held ?? 0) + (stats.draft ?? 0) },
              { label: "Sent", value: stats.sent ?? 0 },
              ...((stats.opened ?? 0) > 0 ? [{ label: "Opened", value: stats.opened }] : []),
              { label: "Replied", value: stats.replied ?? 0 },
              { label: "Bounced", value: stats.bounced ?? 0 },
            ]}
          />
        </Reveal>

        {isLoading ? (
          <Skeleton className="h-40 w-full rounded-2xl" />
        ) : items.length === 0 ? (
          <Bezel tone="muted">
            <EmptyPanel
              compact
              icon={<EnvelopeSimple size={22} weight="light" />}
              title="No recruiter emails yet"
              description="They appear here when an agent prepares an application and finds a recruiter's address."
            />
          </Bezel>
        ) : (
          <>
            {needsYou.length > 0 ? (
              <Reveal>
                <Bezel coreClassName="p-6">
                  <PanelTitle icon={<EnvelopeSimple size={16} weight="light" />} title="Waiting for you" />
                  <ul className="mt-2 divide-y divide-border">
                    {needsYou.map((item) => (
                      <Row key={item.id} item={item} />
                    ))}
                  </ul>
                </Bezel>
              </Reveal>
            ) : null}
            {rest.length > 0 ? (
              <Reveal>
                <Bezel tone="muted" coreClassName="p-6">
                  <PanelTitle icon={<EnvelopeSimple size={16} weight="light" />} title="Queued and sent" />
                  <ul className="mt-2 divide-y divide-border">
                    {rest.map((item) => (
                      <Row key={item.id} item={item} />
                    ))}
                  </ul>
                </Bezel>
              </Reveal>
            ) : null}
          </>
        )}
      </div>
    </Screen>
  );
}
