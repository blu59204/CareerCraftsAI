"use client";

import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "motion/react";
import { Plus, Download, Mail, Calendar, ChevronRight, X, Loader2, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { CommandHeader } from "@/components/immersive/CommandHeader";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";

interface Lead {
  id: string;
  name: string | null;
  email: string | null;
  company: string | null;
  linkedin_url: string | null;
  status: string;
  last_contact: string | null;
  notes: string | null;
}

type UIStatus = "New" | "Contacted" | "Replied" | "Cold";

const STATUS_MAP: Record<string, UIStatus> = {
  cold: "Cold",
  warm: "Contacted",
  hot: "Replied",
  contacted: "Contacted",
  replied: "Replied",
  closed: "Cold",
};

const STATUS_STYLES: Record<UIStatus, string> = {
  New: "bg-primary/15 text-primary",
  Contacted: "bg-warning/15 text-warning",
  Replied: "bg-success/15 text-success",
  Cold: "bg-muted text-muted-foreground",
};

const ACTION_LABEL: Record<UIStatus, string> = {
  New: "Reply",
  Contacted: "Follow up",
  Replied: "Schedule",
  Cold: "Reach out",
};

function getInitials(name: string | null): string {
  if (!name) return "?";
  return name.split(" ").map((p) => p[0]).join("").toUpperCase().slice(0, 2);
}

function relativeTime(iso: string | null): string {
  if (!iso) return "Never";
  const diff = Date.now() - new Date(iso).getTime();
  const h = Math.floor(diff / 3600000);
  if (h < 1) return "Just now";
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d === 1) return "Yesterday";
  if (d < 7) return `${d}d ago`;
  return `${Math.floor(d / 7)}w ago`;
}

interface AddLeadForm {
  name: string;
  company: string;
  email: string;
  linkedin_url: string;
  notes: string;
}

function AddLeadModal({ onClose, onAdd }: { onClose: () => void; onAdd: (lead: Lead) => void }) {
  const [form, setForm] = useState<AddLeadForm>({
    name: "", company: "", email: "", linkedin_url: "", notes: "",
  });
  const [saving, setSaving] = useState(false);

  const set = (k: keyof AddLeadForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) {
      toast.error("Name is required");
      return;
    }
    setSaving(true);
    try {
      const { data } = await apiClient.post("/leads", {
        name: form.name,
        company: form.company || null,
        email: form.email || null,
        linkedin_url: form.linkedin_url || null,
        notes: form.notes || null,
        status: "cold",
      });
      onAdd(data as Lead);
      toast.success(`Lead "${form.name}" added`);
      onClose();
    } catch {
      toast.error("Could not add lead — backend did not save it");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 8 }}
        transition={{ duration: 0.2 }}
        className="relative z-10 w-full max-w-md rounded-3xl border border-border bg-card p-6 shadow-xl"
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-base font-semibold">Add lead</h2>
          <button
            type="button"
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-full hover:bg-secondary"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">Name *</label>
            <input
              value={form.name}
              onChange={set("name")}
              placeholder="Sarah Chen"
              className="h-10 w-full rounded-2xl border border-border bg-background/60 px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">Company</label>
            <input
              value={form.company}
              onChange={set("company")}
              placeholder="Acme Corp"
              className="h-10 w-full rounded-2xl border border-border bg-background/60 px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">Email</label>
            <input
              type="email"
              value={form.email}
              onChange={set("email")}
              placeholder="sarah@acme.com"
              className="h-10 w-full rounded-2xl border border-border bg-background/60 px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">LinkedIn URL</label>
            <input
              value={form.linkedin_url}
              onChange={set("linkedin_url")}
              placeholder="linkedin.com/in/sarahchen"
              className="h-10 w-full rounded-2xl border border-border bg-background/60 px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">Notes</label>
            <textarea
              value={form.notes}
              onChange={set("notes")}
              placeholder="How you found them, context…"
              rows={2}
              className="w-full resize-none rounded-2xl border border-border bg-background/60 px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div className="flex gap-2 pt-1">
            <LiquidGlassButton tone="primary" size="sm" className="flex-1" disabled={saving}>
              {saving ? "Saving…" : "Add lead"}
            </LiquidGlassButton>
            <LiquidGlassButton tone="ghost" size="sm" onClick={onClose} type="button">
              Cancel
            </LiquidGlassButton>
          </div>
        </form>
      </motion.div>
    </div>
  );
}

function LeadDetailModal({ lead, onClose }: { lead: Lead; onClose: () => void }) {
  const uiStatus: UIStatus = STATUS_MAP[lead.status] ?? "Cold";
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 8 }}
        transition={{ duration: 0.2 }}
        className="relative z-10 w-full max-w-md rounded-3xl border border-border bg-card p-6 shadow-xl"
      >
        <div className="mb-5 flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary/15 text-sm font-semibold text-primary">
              {getInitials(lead.name)}
            </div>
            <div>
              <div className="font-semibold">{lead.name ?? "Unknown"}</div>
              <div className="text-sm text-muted-foreground">{lead.company ?? "No company"}</div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-full hover:bg-secondary"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-3">
          <div className="flex items-center justify-between rounded-2xl border border-border bg-card/40 px-4 py-2.5">
            <span className="text-xs text-muted-foreground">Status</span>
            <span className={cn("rounded-full px-3 py-1 text-xs font-medium", STATUS_STYLES[uiStatus])}>
              {uiStatus}
            </span>
          </div>
          <div className="flex items-center justify-between rounded-2xl border border-border bg-card/40 px-4 py-2.5">
            <span className="text-xs text-muted-foreground">Last contact</span>
            <span className="text-sm font-medium">{relativeTime(lead.last_contact)}</span>
          </div>
          {lead.email && (
            <div className="flex items-center justify-between rounded-2xl border border-border bg-card/40 px-4 py-2.5">
              <span className="text-xs text-muted-foreground">Email</span>
              <a href={`mailto:${lead.email}`} className="text-sm text-primary hover:underline" onClick={(e) => e.stopPropagation()}>
                {lead.email}
              </a>
            </div>
          )}
          {lead.linkedin_url && (
            <div className="flex items-center justify-between rounded-2xl border border-border bg-card/40 px-4 py-2.5">
              <span className="text-xs text-muted-foreground">LinkedIn</span>
              <a
                href={lead.linkedin_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-sm text-primary hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                View profile <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          )}
          {lead.notes && (
            <div className="rounded-2xl border border-border bg-card/40 px-4 py-3">
              <div className="mb-1 text-xs text-muted-foreground">Notes</div>
              <p className="text-sm leading-relaxed">{lead.notes}</p>
            </div>
          )}
          <div className="flex gap-2 pt-1">
            <LiquidGlassButton
              tone="primary"
              size="sm"
              className="flex-1"
              onClick={() => {
                toast.info("Open Email page to draft a follow-up");
                onClose();
              }}
            >
              <Mail className="h-3.5 w-3.5" />
              Send email
            </LiquidGlassButton>
            <LiquidGlassButton tone="ghost" size="sm" onClick={onClose}>
              Close
            </LiquidGlassButton>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

export default function LeadsPage() {
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [localLeads, setLocalLeads] = useState<Lead[]>([]);
  const [mutatingLeadId, setMutatingLeadId] = useState<string | null>(null);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImportCsv = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-importing the same file
    if (!file) return;
    setImporting(true);
    try {
      const text = await file.text();
      const rows = text.split(/\r?\n/).map((r) => r.trim()).filter(Boolean);
      if (rows.length === 0) {
        toast.error("CSV is empty");
        return;
      }
      // Detect + skip a header row (name,email,company,linkedin_url)
      const header = rows[0].toLowerCase();
      const dataRows = header.includes("name") && header.includes("email") ? rows.slice(1) : rows;

      let ok = 0;
      for (const row of dataRows) {
        const [name, email, company, linkedin_url] = row.split(",").map((c) => c.trim());
        if (!name) continue;
        try {
          await apiClient.post("/leads", {
            name,
            email: email || null,
            company: company || null,
            linkedin_url: linkedin_url || null,
            status: "cold",
          });
          ok++;
        } catch {
          // skip malformed row, keep going
        }
      }
      qc.invalidateQueries({ queryKey: ["leads"] });
      toast.success(`Imported ${ok} lead${ok === 1 ? "" : "s"} from CSV`);
    } catch {
      toast.error("Could not read CSV file");
    } finally {
      setImporting(false);
    }
  };

  const { data: remoteLeads = [], isLoading } = useQuery<Lead[]>({
    queryKey: ["leads"],
    queryFn: async () => {
      const { data } = await apiClient.get("/leads");
      return data;
    },
  });

  const leads = [...localLeads, ...remoteLeads.filter((l) => !localLeads.find((x) => x.id === l.id))];

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      apiClient.patch(`/leads/${id}/status`, { status }),
    onMutate: ({ id }) => setMutatingLeadId(id),
    onSuccess: () => {
      setMutatingLeadId(null);
      toast.success("Lead status updated");
      qc.invalidateQueries({ queryKey: ["leads"] });
    },
    onError: () => {
      setMutatingLeadId(null);
      toast.error("Failed to update status");
    },
  });

  const contactedCount = leads.filter((l) => l.status === "contacted" || l.status === "warm").length;
  const repliedCount = leads.filter((l) => l.status === "replied" || l.status === "hot").length;
  const replyRate = leads.length > 0 ? ((repliedCount / leads.length) * 100).toFixed(1) : "0.0";

  return (
    <>
      <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
        <motion.div variants={fadeUp}>
          <CommandHeader
            eyebrow="Max Reed Portfolio Features"
            title="Recruiter Contacts"
            description="Manage warm leads, CSV imports, replies, and follow-up status without fake placeholder data."
            actions={
              <div className="flex gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              onChange={handleImportCsv}
              className="hidden"
            />
            <LiquidGlassButton
              tone="ghost"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              disabled={importing}
            >
              <Download className="h-4 w-4" />
              {importing ? "Importing…" : "Import CSV"}
            </LiquidGlassButton>
            <LiquidGlassButton tone="primary" size="sm" onClick={() => setAddOpen(true)}>
              <Plus className="h-4 w-4" />
              Add lead
            </LiquidGlassButton>
              </div>
            }
          />
        </motion.div>

        {/* Stats row */}
        <motion.div variants={fadeUp} className="grid gap-4 md:grid-cols-3">
          <div className="glass-panel rounded-3xl p-6">
            <div className="text-sm text-muted-foreground">Total leads</div>
            {isLoading ? (
              <div className="mt-2 h-8 w-12 shimmer rounded-xl" />
            ) : (
              <div className="mt-2 text-3xl font-semibold">{leads.length}</div>
            )}
          </div>
          <div className="glass-panel rounded-3xl p-6">
            <div className="text-sm text-muted-foreground">Contacted</div>
            {isLoading ? (
              <div className="mt-2 h-8 w-8 shimmer rounded-xl" />
            ) : (
              <div className="mt-2 text-3xl font-semibold">{contactedCount}</div>
            )}
          </div>
          <div className="glass-panel rounded-3xl p-6">
            <div className="text-sm text-muted-foreground">Replied</div>
            {isLoading ? (
              <div className="mt-2 h-8 w-20 shimmer rounded-xl" />
            ) : (
              <div className="mt-2 flex items-baseline gap-3">
                <span className="text-3xl font-semibold">{repliedCount}</span>
                <span className="text-sm text-success">{replyRate}% rate</span>
              </div>
            )}
          </div>
        </motion.div>

        {/* Lead list */}
        <motion.div variants={fadeUp} className="space-y-3">
          <div className="text-sm text-muted-foreground">All contacts</div>
          {isLoading
            ? Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-16 shimmer rounded-3xl" />
              ))
            : leads.map((lead) => {
                const uiStatus: UIStatus = STATUS_MAP[lead.status] ?? "Cold";
                return (
                  <div
                    key={lead.id}
                    onClick={() => setSelectedLead(lead)}
                    className="glass-panel flex cursor-pointer items-center gap-4 rounded-3xl p-4 transition-colors hover:bg-card/80"
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/15 text-sm font-semibold text-primary">
                      {getInitials(lead.name)}
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="font-medium leading-none">{lead.name ?? "Unknown"}</div>
                      <div className="mt-1 truncate text-sm text-muted-foreground">
                        {lead.company ?? "No company"}
                      </div>
                    </div>

                    <div className="hidden shrink-0 text-sm text-muted-foreground md:block w-24 text-right">
                      {relativeTime(lead.last_contact)}
                    </div>

                    <span
                      className={cn(
                        "hidden shrink-0 rounded-full px-3 py-1 text-xs font-medium sm:inline-flex",
                        STATUS_STYLES[uiStatus]
                      )}
                    >
                      {uiStatus}
                    </span>

                    <LiquidGlassButton
                      tone="ghost"
                      size="sm"
                      className="shrink-0 gap-1.5"
                      disabled={mutatingLeadId === lead.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        statusMutation.mutate({
                          id: lead.id,
                          status: uiStatus === "Replied" ? "replied" : "contacted",
                        });
                      }}
                    >
                      {mutatingLeadId === lead.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : uiStatus === "Replied" ? (
                        <Calendar className="h-3.5 w-3.5" />
                      ) : (
                        <Mail className="h-3.5 w-3.5" />
                      )}
                      {ACTION_LABEL[uiStatus]}
                      <ChevronRight className="h-3.5 w-3.5 opacity-50" />
                    </LiquidGlassButton>
                  </div>
                );
              })}
        </motion.div>

        {leads.length === 0 && !isLoading && (
          <motion.div variants={fadeUp}>
            <div className="rounded-3xl border border-dashed border-border bg-card/40 p-6 text-center text-sm text-muted-foreground">
              No leads yet. Add contacts manually or import from LinkedIn.
            </div>
          </motion.div>
        )}
      </motion.div>

      <AnimatePresence>
        {addOpen && (
          <AddLeadModal
            onClose={() => setAddOpen(false)}
            onAdd={(lead) => setLocalLeads((prev) => [lead, ...prev])}
          />
        )}
        {selectedLead && (
          <LeadDetailModal lead={selectedLead} onClose={() => setSelectedLead(null)} />
        )}
      </AnimatePresence>
    </>
  );
}
