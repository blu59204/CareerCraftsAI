"use client";

import { useEffect, useState, type ChangeEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowCounterClockwise,
  Bell,
  Brain,
  Briefcase,
  Camera,
  Check,
  Database,
  Desktop,
  DownloadSimple,
  Fingerprint,
  GithubLogo,
  GoogleLogo,
  IdentificationCard,
  LinkedinLogo,
  Lock,
  Palette,
  Password,
  Plugs,
  SealCheck,
  ShieldCheck,
  SignOut,
  Trash,
  UserCircle,
  Warning,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import { SettingsNav } from "@/components/settings/SettingsNav";
import {
  Bezel,
  Eyebrow,
  Field,
  Hairline,
  IslandButton,
  IslandLink,
  Input,
  Notice,
  PageHero,
  PanelTitle,
  Reveal,
  Screen,
  Segmented,
  Skeleton,
  StatusPill,
  Toggle,
  panelSwap,
} from "@/components/vanguard";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import { connectGmail } from "@/lib/nango-connect";
import { useClerk, useUser } from "@clerk/nextjs";
import { useUserStatus } from "@/components/auth/UserStatusContext";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

// Typed by the member to confirm scheduling deletion.
const DELETE_CONFIRM_PHRASE = "DELETE";

type Tab = "account" | "security" | "notifications";

interface UserProfile {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  headline: string | null;
  phone: string | null;
  linkedin_url: string | null;
  onboarding_completed: boolean;
  deletion_requested_at: string | null;
  deletion_scheduled_for: string | null;
  deletion_cooldown_until: string | null;
}

interface NotificationPreferences {
  notify_email: boolean;
  notify_agent_alerts: boolean;
  notify_followup_reminders: boolean;
  notify_weekly_digest: boolean;
  notify_daily_summary: boolean;
}

function getInitials(fullName: string | null | undefined): string {
  if (!fullName) return "?";
  return fullName
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function formatLongDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

// Preset monogram colors — like Google/Slack's default-avatar color picker.
// Rendered locally via canvas rather than fetched from a hosted avatar
// service, so there's no external URL that can go stale or 404.
const AVATAR_PRESETS = [
  "#1F6F4A", // primary emerald
  "#2563EB",
  "#7C3AED",
  "#DB2777",
  "#DC2626",
  "#D97706",
  "#0891B2",
  "#4B5563",
];

async function renderPresetAvatar(color: string, initials: string): Promise<Blob> {
  const size = 256;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas not supported");
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(size / 2, size / 2, size / 2, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.font = "600 96px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(initials || "?", size / 2, size / 2 + 6);
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("toBlob failed"))), "image/png");
  });
}

/** Pill styling for the <label> that wraps the hidden file input (matches IslandButton ghost/sm). */
const UPLOAD_LABEL_CLASS =
  "group relative inline-flex h-9 cursor-pointer select-none items-center justify-center gap-2 whitespace-nowrap rounded-full bg-card px-4 text-[13px] font-medium tracking-[-0.01em] text-foreground " +
  "ring-1 ring-foreground/10 shadow-bezel-core dark:ring-white/10 dark:shadow-bezel-core-dark " +
  "transition-[background-color,color,box-shadow,transform,opacity] duration-500 ease-vanguard hover:bg-muted/60 active:scale-[0.98] " +
  "focus-within:ring-2 focus-within:ring-ring";

/** Icon medallion used in list rows. */
function Medallion({ children, tone = "default" }: { children: ReactNode; tone?: "default" | "danger" }) {
  return (
    <span
      aria-hidden
      className={cn(
        "grid h-10 w-10 shrink-0 place-items-center rounded-full ring-1",
        tone === "danger"
          ? "bg-danger/10 text-danger ring-danger/20"
          : "bg-foreground/[0.04] text-foreground/80 ring-foreground/[0.06] dark:bg-white/[0.05] dark:ring-white/10",
      )}
    >
      {children}
    </span>
  );
}

/** Title + description block used at the top of each right-column section. */
function SectionIntro({ icon, title, description, meta }: { icon: ReactNode; title: string; description?: ReactNode; meta?: ReactNode }) {
  return (
    <div className="space-y-2">
      <PanelTitle icon={icon} title={title} meta={meta} />
      {description ? <p className="max-w-[62ch] pl-[2.625rem] text-sm leading-6 text-muted-foreground">{description}</p> : null}
    </div>
  );
}

export default function AccountSettingsPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { user: authUser } = useUser();
  const signInEmail = authUser?.primaryEmailAddress?.emailAddress ?? "";
  const signInEmailVerified = authUser?.primaryEmailAddress?.verification?.status === "verified";
  const { signOut } = useClerk();
  const { refresh: refreshUserStatus } = useUserStatus();
  const [activeTab, setActiveTab] = useState<Tab>("account");
  const [deletionActionPending, setDeletionActionPending] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [exporting, setExporting] = useState(false);
  const { data: notifyPrefs } = useQuery<NotificationPreferences>({
    queryKey: ["preferences"],
    queryFn: async () => (await apiClient.get("/users/me/preferences")).data ?? {},
  });
  const emailNotifs = notifyPrefs?.notify_email ?? true;
  const agentAlerts = notifyPrefs?.notify_agent_alerts ?? true;
  const followUpReminders = notifyPrefs?.notify_followup_reminders ?? true;
  const weeklyDigest = notifyPrefs?.notify_weekly_digest ?? false;
  const dailySummary = notifyPrefs?.notify_daily_summary ?? false;
  const saveNotifyPrefs = useMutation({
    mutationFn: async (payload: NotificationPreferences) =>
      apiClient.patch("/users/me/preferences", payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["preferences"] }),
    onError: () => toast.error("Couldn't save notification preferences"),
  });
  const toggleNotifyPref = (key: keyof NotificationPreferences) => {
    const current: NotificationPreferences = {
      notify_email: emailNotifs,
      notify_agent_alerts: agentAlerts,
      notify_followup_reminders: followUpReminders,
      notify_weekly_digest: weeklyDigest,
      notify_daily_summary: dailySummary,
    };
    saveNotifyPrefs.mutate({ ...current, [key]: !current[key] });
  };
  // Two-factor state is owned by the identity provider; the switch only explains that.
  const [twoFactor] = useState(false);
  const [avatarSaving, setAvatarSaving] = useState(false);
  const [presetPickerOpen, setPresetPickerOpen] = useState(false);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [headline, setHeadline] = useState("");
  const [phone, setPhone] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const { data: user, isLoading } = useQuery<UserProfile>({
    queryKey: ["me"],
    queryFn: async () => {
      const { data } = await apiClient.get("/users/me");
      return data as UserProfile;
    },
  });

  const { data: connectedAccounts } = useQuery<{ google: boolean; gmail_send: boolean }>({
    queryKey: ["connected-accounts"],
    queryFn: async () => {
      const { data } = await apiClient.get("/users/me/connected-accounts");
      return data;
    },
  });

  useEffect(() => {
    if (user) {
      setName(user.full_name?.trim() || authUser?.fullName || "");
      setEmail(signInEmail || user.email);
      setHeadline(user.headline ?? "");
      setPhone(user.phone ?? "");
      setLinkedinUrl(user.linkedin_url ?? "");
    }
  }, [authUser?.fullName, signInEmail, user]);

  // Linked social identities live on the auth user as external accounts.
  const externalAccounts = authUser?.externalAccounts ?? [];
  const hasProvider = (provider: string) =>
    externalAccounts.some((account) => account.provider === provider);
  const hasLinkedIn = hasProvider("linkedin_oidc") || hasProvider("linkedin");
  const hasGithub = hasProvider("github");
  const googleAccount = externalAccounts.find((account) => account.provider === "google");
  const googlePhotoUrl = googleAccount?.imageUrl || null;
  const usingGooglePhoto = !!googlePhotoUrl && authUser?.imageUrl === googlePhotoUrl;

  const displayName = user?.full_name || authUser?.fullName || "Add your name";
  const initials = getInitials(user?.full_name || authUser?.fullName);
  const connectionCount = [!!connectedAccounts?.google, hasLinkedIn, hasGithub].filter(Boolean).length;
  const deletionScheduled = !!(user?.deletion_requested_at && user.deletion_scheduled_for);

  const handleAvatarFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/") || file.size > 5 * 1024 * 1024) {
      toast.error("Choose an image smaller than 5 MB.");
      return;
    }
    if (!authUser) return;
    setAvatarSaving(true);
    try {
      await authUser.setProfileImage({ file });
      toast.success("Profile photo updated");
    } catch {
      toast.error("Could not update profile photo.");
    } finally {
      setAvatarSaving(false);
    }
  };

  const applyPreset = async (color: string) => {
    if (!authUser) return;
    setAvatarSaving(true);
    try {
      const blob = await renderPresetAvatar(color, getInitials(user?.full_name || authUser?.fullName));
      await authUser.setProfileImage({ file: blob });
      toast.success("Profile photo updated");
      setPresetPickerOpen(false);
    } catch {
      toast.error("Could not update profile photo.");
    } finally {
      setAvatarSaving(false);
    }
  };

  const applyGooglePhoto = async () => {
    if (!authUser || !googlePhotoUrl) return;
    setAvatarSaving(true);
    try {
      const res = await fetch(googlePhotoUrl);
      const blob = await res.blob();
      await authUser.setProfileImage({ file: blob });
      toast.success("Using your Google profile photo");
    } catch {
      toast.error("Could not fetch your Google photo.");
    } finally {
      setAvatarSaving(false);
    }
  };

  const handleManageAuth = () => {
    toast.info("Sign in with the provider from the login page to link it to this account.");
  };

  const handleSignOut = async () => {
    await signOut();
    router.push("/");
  };

  const handleConnectGoogle = async () => {
    const { error } = await connectGmail("/settings/account");
    if (error) toast.error(error.message);
  };

  const handleExportData = async () => {
    setExporting(true);
    try {
      const response = await apiClient.get("/users/me/export", {
        responseType: "blob",
      });
      const blob = new Blob([response.data], { type: "application/zip" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const disposition = response.headers["content-disposition"] as string | undefined;
      const match = disposition?.match(/filename="?([^"]+)"?/);
      a.download = match?.[1] ?? "careercraft-data-export.zip";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Download started");
    } catch {
      toast.error("Failed to export your data — please try again");
    } finally {
      setExporting(false);
    }
  };

  const handleCancelDeletion = async () => {
    setDeletionActionPending(true);
    try {
      await apiClient.post("/users/me/cancel-deletion");
      toast.success("Account deletion cancelled");
      queryClient.invalidateQueries({ queryKey: ["me"] });
      refreshUserStatus();
    } catch {
      toast.error("Couldn't cancel deletion — please try again");
    } finally {
      setDeletionActionPending(false);
    }
  };

  const handleScheduleDeletion = async () => {
    if (deleteConfirmText.trim() !== DELETE_CONFIRM_PHRASE) return;
    setDeleteDialogOpen(false);
    setDeleteConfirmText("");
    setDeletionActionPending(true);
    try {
      await apiClient.delete("/users/me");
      try {
        sessionStorage.setItem("cc-deletion-seen", "1");
      } catch {
        // ignore — nothing more we can do without storage
      }
      toast.success("Account deletion scheduled. Sign in again within 15 days to cancel it.");
      // Deleting ends the session; signing back in shows the cancel option.
      await handleSignOut();
      return;
    } catch (err) {
      const detail = (
        err as {
          response?: { status?: number; data?: { detail?: { cooldown_until?: string } } };
        }
      )?.response;
      if (detail?.status === 429 && detail.data?.detail?.cooldown_until) {
        const until = formatLongDate(detail.data.detail.cooldown_until);
        toast.error(`You cancelled a deletion recently — try again after ${until}.`);
      } else {
        toast.error("Failed to delete account — please try again or contact support");
      }
    } finally {
      setDeletionActionPending(false);
    }
  };

  const updateMutation = useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.patch("/users/me", {
        full_name: name || undefined,
        headline: headline || undefined,
        phone: phone || undefined,
        linkedin_url: linkedinUrl || undefined,
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      toast.success("Profile updated");
    },
    onError: () => toast.error("Update failed"),
  });

  const disconnectGoogleMutation = useMutation({
    mutationFn: async () => apiClient.delete("/integrations/gmail"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["connected-accounts"] });
      toast.info("Google disconnected");
    },
    onError: () => toast.error("Could not disconnect Google"),
  });

  const tabs: { id: Tab; label: string; icon: ReactNode }[] = [
    { id: "account", label: "Account", icon: <IdentificationCard size={15} weight="light" /> },
    { id: "security", label: "Security", icon: <ShieldCheck size={15} weight="light" /> },
    { id: "notifications", label: "Notifications", icon: <Bell size={15} weight="light" /> },
  ];

  const notificationItems = [
    { key: "notify_email" as const, label: "Email notifications", sub: "Receive updates via email", enabled: emailNotifs },
    { key: "notify_agent_alerts" as const, label: "Agent completion alerts", sub: "Notify when agents finish running", enabled: agentAlerts },
    { key: "notify_followup_reminders" as const, label: "Follow-up reminders", sub: "Reminders to follow up with leads", enabled: followUpReminders },
    { key: "notify_weekly_digest" as const, label: "Weekly digest", sub: "A weekly summary of your activity", enabled: weeklyDigest },
    { key: "notify_daily_summary" as const, label: "Daily summary", sub: "Each day: applications sent, replies and what needs you", enabled: dailySummary },
  ];
  const enabledNotificationCount = notificationItems.filter((item) => item.enabled).length;

  const connectedPill = (
    <StatusPill tone="success" icon={<Check size={11} weight="light" />}>
      Connected
    </StatusPill>
  );

  return (
    <Screen className="space-y-6 md:space-y-8">
      <PageHero
        eyebrow="Settings"
        title="Account Settings"
        description="Your identity, sign-in security, connected accounts and the alerts CareerCraft sends you."
        aside={
          <Bezel size="md" lifted coreClassName="p-5 md:p-6">
            <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">At a glance</p>
            <dl className="mt-4 space-y-3.5 text-sm">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-muted-foreground">Sign-in email</dt>
                <dd>
                  {signInEmailVerified ? (
                    <StatusPill tone="success">Verified</StatusPill>
                  ) : (
                    <StatusPill tone="neutral">Unverified</StatusPill>
                  )}
                </dd>
              </div>
              <Hairline />
              <div className="flex items-center justify-between gap-3">
                <dt className="text-muted-foreground">Linked accounts</dt>
                <dd className="font-medium tabular-nums text-foreground">{connectionCount} of 3</dd>
              </div>
              <Hairline />
              <div className="flex items-center justify-between gap-3">
                <dt className="text-muted-foreground">Status</dt>
                <dd>
                  {deletionScheduled ? (
                    <StatusPill tone="danger" live>Deletion pending</StatusPill>
                  ) : (
                    <StatusPill tone="primary">Active</StatusPill>
                  )}
                </dd>
              </div>
            </dl>
          </Bezel>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:gap-10">
        {/* ── Left: sticky identity column ─────────────────────────────── */}
        <aside aria-label="Your identity" className="min-w-0 lg:col-span-4 lg:self-start lg:sticky lg:top-24">
          <div className="space-y-6">
            <Reveal>
              <Bezel lifted coreClassName="p-6 md:p-7">
                <div className="flex items-start gap-4 lg:flex-col lg:gap-5">
                  <div className="relative shrink-0">
                    <div className="grid h-20 w-20 place-items-center overflow-hidden rounded-[1.4rem] bg-primary/10 text-xl font-semibold tracking-[-0.02em] text-primary ring-1 ring-primary/15 lg:h-24 lg:w-24 lg:rounded-[1.6rem]">
                      {authUser?.imageUrl ? (
                        // eslint-disable-next-line @next/next/no-img-element -- Clerk-hosted avatar, dynamic origin
                        <img src={authUser.imageUrl} alt="Profile" className="h-full w-full object-cover" />
                      ) : isLoading ? (
                        <Skeleton className="h-full w-full rounded-none" />
                      ) : (
                        initials
                      )}
                    </div>
                    {avatarSaving ? (
                      <span aria-hidden className="absolute inset-0 overflow-hidden rounded-[1.4rem] bg-background/50 lg:rounded-[1.6rem]">
                        <Skeleton className="h-full w-full rounded-none opacity-70" />
                      </span>
                    ) : null}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-geist text-xl font-semibold tracking-[-0.03em] text-foreground">
                      {isLoading ? <Skeleton className="h-6 w-36 rounded-full" /> : displayName}
                    </div>
                    <div className="mt-1 break-all text-sm text-muted-foreground">
                      {isLoading ? <Skeleton className="mt-1 h-4 w-48 rounded-full" /> : signInEmail || user?.email || ""}
                    </div>
                    {signInEmailVerified ? (
                      <StatusPill tone="success" icon={<SealCheck size={12} weight="light" />} className="mt-3">
                        Verified sign-in email
                      </StatusPill>
                    ) : null}
                  </div>
                </div>

                <Hairline className="my-6" />

                <div className="space-y-3">
                  <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">Profile photo</p>
                  <div className="flex flex-wrap gap-2">
                    <label className={cn(UPLOAD_LABEL_CLASS, avatarSaving && "pointer-events-none opacity-50")}>
                      <Camera aria-hidden size={14} weight="light" />
                      {avatarSaving ? "Uploading photo…" : "Upload photo"}
                      <input
                        type="file"
                        accept="image/*"
                        className="sr-only"
                        disabled={avatarSaving}
                        onChange={handleAvatarFile}
                      />
                    </label>
                    <IslandButton
                      tone="ghost"
                      size="sm"
                      disabled={avatarSaving}
                      aria-expanded={presetPickerOpen}
                      aria-controls="avatar-preset-picker"
                      icon={<Palette size={14} weight="light" />}
                      onClick={() => setPresetPickerOpen((v) => !v)}
                    >
                      Choose a preset
                    </IslandButton>
                    {googlePhotoUrl && !usingGooglePhoto && (
                      <IslandButton
                        tone="quiet"
                        size="sm"
                        disabled={avatarSaving}
                        icon={<GoogleLogo size={14} weight="light" />}
                        onClick={applyGooglePhoto}
                      >
                        Use Google photo
                      </IslandButton>
                    )}
                  </div>
                  <AnimatePresence initial={false}>
                    {presetPickerOpen && (
                      <motion.div
                        id="avatar-preset-picker"
                        key="preset-picker"
                        variants={panelSwap}
                        initial="hidden"
                        animate="show"
                        exit="exit"
                        role="group"
                        aria-label="Preset avatars"
                        className="grid grid-cols-8 gap-2 rounded-2xl bg-foreground/[0.03] p-2 ring-1 ring-foreground/[0.06] dark:bg-white/[0.03] dark:ring-white/10 lg:grid-cols-4"
                      >
                        {AVATAR_PRESETS.map((color) => (
                          <button
                            key={color}
                            type="button"
                            disabled={avatarSaving}
                            onClick={() => applyPreset(color)}
                            aria-label={`Use ${color} preset avatar`}
                            className="mx-auto grid aspect-square w-full max-w-10 place-items-center rounded-full text-[11px] font-semibold text-white ring-2 ring-transparent ring-offset-2 ring-offset-card transition-[transform,box-shadow] duration-500 ease-vanguard hover:scale-105 hover:ring-ring focus-visible:outline-none focus-visible:ring-ring active:scale-95 disabled:opacity-60"
                            style={{ backgroundColor: color }}
                          >
                            {initials}
                          </button>
                        ))}
                      </motion.div>
                    )}
                  </AnimatePresence>
                  <p aria-live="polite" className="sr-only">
                    {avatarSaving ? "Updating profile photo" : ""}
                  </p>
                </div>
              </Bezel>
            </Reveal>

            <Reveal delay={0.06} className="settings-nav-vertical space-y-3">
              <Eyebrow>All settings</Eyebrow>
              <SettingsNav />
            </Reveal>
          </div>
        </aside>

        {/* ── Right: working column ────────────────────────────────────── */}
        <div className="min-w-0 space-y-6 lg:col-span-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Segmented<Tab>
              ariaLabel="Settings view"
              value={activeTab}
              onChange={setActiveTab}
              options={tabs.map((t) => ({ value: t.id, label: t.label, icon: t.icon }))}
            />
            {activeTab === "notifications" ? (
              <span aria-live="polite" className="text-xs text-muted-foreground">
                {saveNotifyPrefs.isPending ? "Saving…" : `${enabledNotificationCount} of ${notificationItems.length} on`}
              </span>
            ) : null}
          </div>

          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={activeTab}
              role="tabpanel"
              aria-label={tabs.find((t) => t.id === activeTab)?.label}
              variants={panelSwap}
              initial="hidden"
              animate="show"
              exit="exit"
              className="space-y-6"
            >
              {/* ── Account tab ─────────────────────────────────────── */}
              {activeTab === "account" && (
                <>
                  <Reveal subtle>
                    <Bezel coreClassName="p-6 md:p-8">
                      <SectionIntro
                        icon={<UserCircle size={16} weight="light" />}
                        title="Profile"
                        description="How agents introduce you in outreach, cover letters and applications."
                      />
                      <form
                        noValidate
                        className="mt-7 space-y-5"
                        onSubmit={(e) => {
                          e.preventDefault();
                          updateMutation.mutate();
                        }}
                      >
                        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                          <Field label="Name">
                            {(id) => (
                              <Input
                                id={id}
                                type="text"
                                autoComplete="name"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                placeholder="Your full name"
                              />
                            )}
                          </Field>
                          <Field
                            label="Contact email"
                            hint="Your sign-in email is managed by your identity provider and can’t be changed here."
                          >
                            {(id) => (
                              <Input
                                id={id}
                                type="email"
                                value={email}
                                readOnly
                                placeholder="Your sign-in email"
                                className="cursor-not-allowed text-muted-foreground"
                                trailing={<Lock aria-hidden size={14} weight="light" className="text-muted-foreground" />}
                              />
                            )}
                          </Field>
                        </div>
                        <Field label="Headline">
                          {(id) => (
                            <Input
                              id={id}
                              type="text"
                              value={headline}
                              onChange={(e) => setHeadline(e.target.value)}
                              placeholder="e.g. Senior Software Engineer at Stripe"
                            />
                          )}
                        </Field>
                        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                          <Field label="Phone">
                            {(id) => (
                              <Input
                                id={id}
                                type="tel"
                                autoComplete="tel"
                                value={phone}
                                onChange={(e) => setPhone(e.target.value)}
                                placeholder="+1 555 000 0000"
                                className="tabular-nums"
                              />
                            )}
                          </Field>
                          <Field label="LinkedIn URL">
                            {(id) => (
                              <Input
                                id={id}
                                type="url"
                                value={linkedinUrl}
                                onChange={(e) => setLinkedinUrl(e.target.value)}
                                placeholder="https://linkedin.com/in/your-profile"
                              />
                            )}
                          </Field>
                        </div>
                        <Hairline />
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <p className="text-xs text-muted-foreground">Changes apply to every agent on its next run.</p>
                          <IslandButton type="submit" size="md" disabled={updateMutation.isPending} trailing={<Check size={15} weight="light" />}>
                            {updateMutation.isPending ? "Saving…" : "Save changes"}
                          </IslandButton>
                        </div>
                      </form>
                    </Bezel>
                  </Reveal>

                  {/* Shortcuts: job preferences + models — asymmetric pair */}
                  <div className="grid grid-cols-1 gap-6 md:grid-cols-5">
                    <Reveal subtle className="md:col-span-3">
                      <Bezel size="md" tone="primary" className="h-full" coreClassName="flex h-full flex-col p-6">
                        <PanelTitle icon={<Briefcase size={16} weight="light" />} title="Job preferences" />
                        <p className="mt-3 flex-1 text-sm leading-6 text-muted-foreground">
                          Set your target role, experience level, work mode and salary on the Jobs page.
                        </p>
                        <div className="mt-5">
                          <IslandLink href="/jobs#search-profile" tone="ghost" size="sm" trailing>
                            Manage preferences
                          </IslandLink>
                        </div>
                      </Bezel>
                    </Reveal>
                    <Reveal subtle delay={0.05} className="md:col-span-2">
                      <Bezel size="md" className="h-full" coreClassName="flex h-full flex-col p-6">
                        <PanelTitle icon={<Brain size={16} weight="light" />} title="AI models & API keys" />
                        <p className="mt-3 flex-1 text-sm leading-6 text-muted-foreground">
                          Add your Anthropic, OpenAI, Google, or Ollama API key. Agents use your key — BYOK.
                        </p>
                        <div className="mt-5">
                          <IslandLink href="/settings/models" tone="ghost" size="sm" trailing>
                            Manage models
                          </IslandLink>
                        </div>
                      </Bezel>
                    </Reveal>
                  </div>

                  {/* Connected accounts */}
                  <Reveal subtle>
                    <Bezel coreClassName="p-6 md:p-8">
                      <SectionIntro
                        icon={<Plugs size={16} weight="light" />}
                        title="Connected accounts"
                        meta={
                          <IslandLink href="/settings/integrations" tone="quiet" size="sm">
                            Manage integrations
                          </IslandLink>
                        }
                      />
                      <ul className="mt-6 divide-y divide-foreground/[0.07] dark:divide-white/[0.07]">
                        <li className="flex flex-col gap-4 py-4 first:pt-0 sm:flex-row sm:items-center sm:justify-between">
                          <div className="flex items-center gap-3.5">
                            <Medallion><GoogleLogo size={18} weight="light" /></Medallion>
                            <div>
                              <p className="text-sm font-medium text-foreground">Google</p>
                              <p className="text-xs text-muted-foreground">Used for Gmail agent</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2.5 pl-[3.5rem] sm:pl-0">
                            {connectedAccounts?.google ? (
                              <>
                                {connectedPill}
                                <IslandButton
                                  tone="ghost"
                                  size="sm"
                                  disabled={disconnectGoogleMutation.isPending}
                                  onClick={() => disconnectGoogleMutation.mutate()}
                                >
                                  Disconnect
                                </IslandButton>
                              </>
                            ) : (
                              <IslandButton tone="primary" size="sm" onClick={handleConnectGoogle}>
                                Connect
                              </IslandButton>
                            )}
                          </div>
                        </li>
                        <li className="flex flex-col gap-4 py-4 sm:flex-row sm:items-center sm:justify-between">
                          <div className="flex items-center gap-3.5">
                            <Medallion><LinkedinLogo size={18} weight="light" /></Medallion>
                            <div>
                              <p className="text-sm font-medium text-foreground">LinkedIn</p>
                              <p className="text-xs text-muted-foreground">For profile optimization</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2.5 pl-[3.5rem] sm:pl-0">
                            {hasLinkedIn && connectedPill}
                            <IslandButton tone={hasLinkedIn ? "ghost" : "primary"} size="sm" onClick={handleManageAuth}>
                              {hasLinkedIn ? "Manage" : "Connect"}
                            </IslandButton>
                          </div>
                        </li>
                        <li className="flex flex-col gap-4 py-4 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
                          <div className="flex items-center gap-3.5">
                            <Medallion><GithubLogo size={18} weight="light" /></Medallion>
                            <div>
                              <p className="text-sm font-medium text-foreground">GitHub</p>
                              <p className="text-xs text-muted-foreground">Portfolio &amp; projects</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2.5 pl-[3.5rem] sm:pl-0">
                            {hasGithub ? (
                              <>
                                {connectedPill}
                                <IslandButton tone="ghost" size="sm" onClick={handleManageAuth}>Manage</IslandButton>
                              </>
                            ) : (
                              <IslandButton tone="primary" size="sm" onClick={handleManageAuth}>Connect</IslandButton>
                            )}
                          </div>
                        </li>
                      </ul>
                    </Bezel>
                  </Reveal>

                  {/* Your data */}
                  <Reveal subtle>
                    <Bezel tone="muted" coreClassName="grid grid-cols-1 gap-6 p-6 md:grid-cols-[1fr_auto] md:items-center md:p-8">
                      <SectionIntro
                        icon={<Database size={16} weight="light" />}
                        title="Your data"
                        description="Download every record CareerCraft AI stores for your account — profile, resumes, applications, agent runs, and more — as a ZIP of JSON files. Encrypted credentials (API keys, saved LinkedIn sign-in) are excluded for your own security."
                      />
                      <IslandButton
                        tone="primary"
                        size="sm"
                        disabled={exporting}
                        aria-busy={exporting}
                        icon={<DownloadSimple size={14} weight="light" />}
                        onClick={handleExportData}
                        className="justify-self-start md:justify-self-end"
                      >
                        Download my data (.zip)
                      </IslandButton>
                    </Bezel>
                  </Reveal>

                  {/* Danger zone */}
                  <Reveal subtle>
                    <Bezel tone="danger" coreClassName="p-6 md:p-8">
                      <div className="flex items-center gap-2.5">
                        <Medallion tone="danger"><Warning size={16} weight="light" /></Medallion>
                        <h3 className="font-geist text-[15px] font-semibold tracking-[-0.015em] text-danger">Danger zone</h3>
                      </div>
                      {deletionScheduled && user?.deletion_scheduled_for ? (
                        <div className="mt-5 space-y-5">
                          <Notice tone="warning" icon={<Warning size={16} weight="light" />}>
                            Your account is scheduled for deletion on{" "}
                            <strong className="font-semibold text-foreground">{formatLongDate(user.deletion_scheduled_for)}</strong>
                            . You can cancel any time before then.
                          </Notice>
                          <IslandButton
                            tone="ghost"
                            size="sm"
                            disabled={deletionActionPending}
                            icon={<ArrowCounterClockwise size={14} weight="light" />}
                            onClick={handleCancelDeletion}
                          >
                            {deletionActionPending ? "Cancelling…" : "Cancel deletion"}
                          </IslandButton>
                        </div>
                      ) : (
                        <div className="mt-4 grid grid-cols-1 gap-5 md:grid-cols-[1fr_auto] md:items-end">
                          <p className="max-w-[62ch] text-sm leading-6 text-muted-foreground">
                            Deleting your account starts a 15-day grace period — your data isn&apos;t removed
                            immediately, and you can cancel any time before then. If you cancel, you&apos;ll need
                            to wait 30 days before requesting deletion again.
                          </p>
                          <IslandButton
                            tone="danger"
                            size="sm"
                            disabled={deletionActionPending}
                            icon={<Trash size={14} weight="light" />}
                            onClick={() => setDeleteDialogOpen(true)}
                            className="justify-self-start md:justify-self-end"
                          >
                            {deletionActionPending ? "Scheduling…" : "Delete my account"}
                          </IslandButton>
                          <Dialog
                            open={deleteDialogOpen}
                            onOpenChange={(open) => {
                              setDeleteDialogOpen(open);
                              if (!open) setDeleteConfirmText("");
                            }}
                          >
                            <DialogContent className="w-[calc(100%-2rem)] rounded-3xl border-border bg-card p-5 sm:p-6">
                              <DialogTitle>Delete your account?</DialogTitle>
                              <DialogDescription className="leading-6">
                                Your data will be permanently removed after a 15-day grace period. You can cancel
                                any time before then.
                              </DialogDescription>
                              <form
                                className="mt-2 space-y-4"
                                onSubmit={(event) => {
                                  event.preventDefault();
                                  void handleScheduleDeletion();
                                }}
                              >
                                <label htmlFor="delete-confirm" className="block text-sm text-muted-foreground">
                                  Type <span className="font-geist-mono font-semibold text-foreground">{DELETE_CONFIRM_PHRASE}</span> to confirm.
                                </label>
                                <Input
                                  id="delete-confirm"
                                  autoFocus
                                  autoComplete="off"
                                  value={deleteConfirmText}
                                  onChange={(event: ChangeEvent<HTMLInputElement>) => setDeleteConfirmText(event.target.value)}
                                  placeholder={DELETE_CONFIRM_PHRASE}
                                />
                                <div className="flex justify-end gap-2">
                                  <IslandButton type="button" tone="ghost" size="sm" onClick={() => setDeleteDialogOpen(false)}>
                                    Cancel
                                  </IslandButton>
                                  <IslandButton
                                    type="submit"
                                    tone="danger"
                                    size="sm"
                                    disabled={deleteConfirmText.trim() !== DELETE_CONFIRM_PHRASE || deletionActionPending}
                                    icon={<Trash size={14} weight="light" />}
                                  >
                                    Delete my account
                                  </IslandButton>
                                </div>
                              </form>
                            </DialogContent>
                          </Dialog>
                        </div>
                      )}
                    </Bezel>
                  </Reveal>
                </>
              )}

              {/* ── Security tab ────────────────────────────────────── */}
              {activeTab === "security" && (
                <>
                  <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                    <Reveal subtle>
                      <Bezel className="h-full" coreClassName="flex h-full flex-col p-6 md:p-7">
                        <PanelTitle icon={<Password size={16} weight="light" />} title="Change password" />
                        <p className="mt-3 flex-1 text-sm leading-6 text-muted-foreground">
                          Passwords and connected login methods are managed by your identity provider.
                        </p>
                        <div className="mt-6">
                          <IslandButton
                            tone="primary"
                            size="sm"
                            onClick={() => toast.info("Use the password reset flow on the login page to change your password.")}
                          >
                            Manage password
                          </IslandButton>
                        </div>
                      </Bezel>
                    </Reveal>
                    <Reveal subtle delay={0.05}>
                      <Bezel className="h-full" coreClassName="flex h-full flex-col p-6 md:p-7">
                        <PanelTitle icon={<Fingerprint size={16} weight="light" />} title="Two-factor authentication" />
                        <p className="mt-3 flex-1 text-sm leading-6 text-muted-foreground">
                          A second step at sign-in, handled by your identity provider.
                        </p>
                        <div className="mt-6 flex items-center justify-between gap-4 rounded-2xl bg-foreground/[0.03] px-4 py-3 ring-1 ring-foreground/[0.06] dark:bg-white/[0.03] dark:ring-white/10">
                          <span className="text-sm text-muted-foreground">
                            Currently: <span className="font-medium text-foreground">{twoFactor ? "enabled" : "disabled"}</span>
                          </span>
                          <Toggle
                            label="Two-factor authentication"
                            checked={twoFactor}
                            onChange={() => toast.info("Two-factor authentication is managed by your identity provider.")}
                          />
                        </div>
                      </Bezel>
                    </Reveal>
                  </div>

                  <Reveal subtle>
                    <Bezel coreClassName="p-6 md:p-8">
                      <SectionIntro icon={<Desktop size={16} weight="light" />} title="Active sessions" />
                      <div className="mt-6 flex flex-col gap-3 rounded-2xl bg-foreground/[0.03] px-4 py-3.5 ring-1 ring-foreground/[0.06] dark:bg-white/[0.03] dark:ring-white/10 sm:flex-row sm:items-center sm:justify-between">
                        <div className="text-sm">
                          <span className="font-medium text-foreground">Current session</span>
                          <span className="text-muted-foreground"> · Chrome · Windows</span>
                        </div>
                        <StatusPill tone="success" live>Active</StatusPill>
                      </div>
                      <Hairline className="my-6" />
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <p className="text-xs text-muted-foreground">Signing out ends this session on this device.</p>
                        <IslandButton tone="ghost" size="sm" icon={<SignOut size={14} weight="light" />} onClick={handleSignOut}>
                          Log out
                        </IslandButton>
                      </div>
                    </Bezel>
                  </Reveal>
                </>
              )}

              {/* ── Notifications tab ───────────────────────────────── */}
              {activeTab === "notifications" && (
                <Reveal subtle>
                  <Bezel coreClassName="p-6 md:p-8">
                    <SectionIntro
                      icon={<Bell size={16} weight="light" />}
                      title="Notification preferences"
                      description="Choose what CareerCraft tells you about. Changes save instantly."
                    />
                    <ul className="mt-6 divide-y divide-foreground/[0.07] dark:divide-white/[0.07]">
                      {notificationItems.map((item) => (
                        <li key={item.key} className="flex items-center justify-between gap-6 py-4 first:pt-0 last:pb-0">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-foreground">{item.label}</p>
                            <p className="mt-0.5 text-xs text-muted-foreground">{item.sub}</p>
                          </div>
                          <Toggle
                            label={item.label}
                            checked={item.enabled}
                            onChange={() => toggleNotifyPref(item.key)}
                          />
                        </li>
                      ))}
                    </ul>
                  </Bezel>
                </Reveal>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </Screen>
  );
}
