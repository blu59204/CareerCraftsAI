"use client";

import { motion } from "motion/react";
import { useState } from "react";
import { User, Shield, Bell, Check, X, Github, Globe, AlertTriangle } from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { cn } from "@/lib/utils";

type Tab = "account" | "security" | "notifications";

interface ToggleProps {
  enabled: boolean;
  onToggle: () => void;
}

function Toggle({ enabled, onToggle }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      onClick={onToggle}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none",
        enabled ? "bg-primary" : "bg-muted",
      )}
    >
      <span
        className={cn(
          "pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-md ring-0 transition-transform",
          enabled ? "translate-x-5" : "translate-x-0",
        )}
      />
    </button>
  );
}

export default function AccountSettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("account");
  const [emailNotifs, setEmailNotifs] = useState(true);
  const [agentAlerts, setAgentAlerts] = useState(true);
  const [followUpReminders, setFollowUpReminders] = useState(true);
  const [weeklyDigest, setWeeklyDigest] = useState(false);
  const [twoFactor, setTwoFactor] = useState(false);

  const tabs: { id: Tab; label: string }[] = [
    { id: "account", label: "Account" },
    { id: "security", label: "Security" },
    { id: "notifications", label: "Notifications" },
  ];

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      {/* Header */}
      <motion.div variants={fadeUp}>
        <div className="text-sm text-muted-foreground">Settings</div>
        <h1 className="mt-1 text-3xl font-medium">Account</h1>
      </motion.div>

      {/* Tab navigation */}
      <motion.div variants={fadeUp} className="flex gap-1 rounded-2xl border border-border bg-card/40 p-1 w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "rounded-xl px-4 py-2 text-sm font-medium transition-colors",
              activeTab === tab.id
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {tab.label}
          </button>
        ))}
      </motion.div>

      {/* Account tab */}
      {activeTab === "account" && (
        <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-6">
          {/* Profile card */}
          <motion.div variants={fadeUp} className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="mb-6 text-sm font-medium">Profile</div>
            <div className="flex items-center gap-4 mb-6">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/20 text-lg font-semibold text-primary">
                JD
              </div>
              <div>
                <div className="font-medium">John Doe</div>
                <div className="text-sm text-muted-foreground">user@example.com</div>
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium">Name</label>
                <input
                  type="text"
                  defaultValue="John Doe"
                  className="w-full rounded-2xl border border-border bg-card/40 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium">
                  Email
                  <span className="ml-2 rounded-full bg-green-500/15 px-2 py-0.5 text-xs font-normal text-green-600">
                    Connected via Supabase
                  </span>
                </label>
                <input
                  type="email"
                  value="user@example.com"
                  disabled
                  className="w-full rounded-2xl border border-border bg-muted/40 px-4 py-2.5 text-sm text-muted-foreground cursor-not-allowed"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium">Bio</label>
                <textarea
                  rows={3}
                  placeholder="Tell us a bit about yourself..."
                  className="w-full rounded-2xl border border-border bg-card/40 px-4 py-2.5 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <LiquidGlassButton tone="primary" size="sm">Save changes</LiquidGlassButton>
            </div>
          </motion.div>

          {/* Connected accounts */}
          <motion.div variants={fadeUp} className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="mb-6 text-sm font-medium">Connected accounts</div>
            <div className="space-y-4">
              {/* Google */}
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-card border border-border">
                    <Globe className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm font-medium">Google</div>
                    <div className="text-xs text-muted-foreground">Used for Gmail agent</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1 rounded-full bg-green-500/15 px-2.5 py-1 text-xs font-medium text-green-600">
                    <Check className="h-3 w-3" /> Connected
                  </span>
                  <LiquidGlassButton tone="ghost" size="sm">Disconnect</LiquidGlassButton>
                </div>
              </div>
              {/* LinkedIn */}
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-card border border-border">
                    <User className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm font-medium">LinkedIn</div>
                    <div className="text-xs text-muted-foreground">For profile optimization</div>
                  </div>
                </div>
                <LiquidGlassButton tone="primary" size="sm">Connect</LiquidGlassButton>
              </div>
              {/* GitHub */}
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-card border border-border">
                    <Github className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm font-medium">GitHub</div>
                    <div className="text-xs text-muted-foreground">Portfolio & projects</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1 rounded-full bg-green-500/15 px-2.5 py-1 text-xs font-medium text-green-600">
                    <Check className="h-3 w-3" /> Connected
                  </span>
                  <LiquidGlassButton tone="ghost" size="sm">Disconnect</LiquidGlassButton>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Danger zone */}
          <motion.div variants={fadeUp} className="rounded-3xl border border-red-500/30 bg-card/60 p-6">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-red-600">
              <AlertTriangle className="h-4 w-4" />
              Danger zone
            </div>
            <p className="mb-4 text-sm text-muted-foreground">
              Once you delete your account, all of your data will be permanently removed. This action
              cannot be undone.
            </p>
            <LiquidGlassButton
              tone="ghost"
              size="sm"
              className="bg-red-500 text-white hover:bg-red-600 hover:opacity-100"
            >
              Delete my account
            </LiquidGlassButton>
          </motion.div>
        </motion.div>
      )}

      {/* Security tab */}
      {activeTab === "security" && (
        <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-6">
          {/* Password change */}
          <motion.div variants={fadeUp} className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="mb-6 text-sm font-medium">Change password</div>
            <div className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium">Current password</label>
                <input
                  type="password"
                  placeholder="••••••••"
                  className="w-full rounded-2xl border border-border bg-card/40 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium">New password</label>
                <input
                  type="password"
                  placeholder="••••••••"
                  className="w-full rounded-2xl border border-border bg-card/40 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium">Confirm new password</label>
                <input
                  type="password"
                  placeholder="••••••••"
                  className="w-full rounded-2xl border border-border bg-card/40 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <LiquidGlassButton tone="primary" size="sm">Update password</LiquidGlassButton>
            </div>
          </motion.div>

          {/* 2FA */}
          <motion.div variants={fadeUp} className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium">Two-factor authentication</div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  Currently: {twoFactor ? "enabled" : "disabled"}
                </div>
              </div>
              <Toggle enabled={twoFactor} onToggle={() => setTwoFactor((v) => !v)} />
            </div>
          </motion.div>

          {/* Active sessions */}
          <motion.div variants={fadeUp} className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="mb-4 text-sm font-medium">Active sessions</div>
            <div className="flex items-center justify-between rounded-2xl bg-card/40 border border-border px-4 py-3">
              <div className="text-sm">
                <span className="font-medium">Current session</span>
                <span className="text-muted-foreground"> · Chrome · Windows</span>
              </div>
              <span className="rounded-full bg-green-500/15 px-2.5 py-1 text-xs font-medium text-green-600">
                Active
              </span>
            </div>
          </motion.div>
        </motion.div>
      )}

      {/* Notifications tab */}
      {activeTab === "notifications" && (
        <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-4">
          <motion.div variants={fadeUp} className="rounded-3xl border border-border bg-card/60 p-6 space-y-5">
            <div className="text-sm font-medium">Notification preferences</div>

            {[
              { label: "Email notifications", sub: "Receive updates via email", enabled: emailNotifs, toggle: () => setEmailNotifs((v) => !v) },
              { label: "Agent completion alerts", sub: "Notify when agents finish running", enabled: agentAlerts, toggle: () => setAgentAlerts((v) => !v) },
              { label: "Follow-up reminders", sub: "Reminders to follow up with leads", enabled: followUpReminders, toggle: () => setFollowUpReminders((v) => !v) },
              { label: "Weekly digest", sub: "A weekly summary of your activity", enabled: weeklyDigest, toggle: () => setWeeklyDigest((v) => !v) },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-sm font-medium">{item.label}</div>
                  <div className="text-xs text-muted-foreground">{item.sub}</div>
                </div>
                <Toggle enabled={item.enabled} onToggle={item.toggle} />
              </div>
            ))}
          </motion.div>
        </motion.div>
      )}
    </motion.div>
  );
}
