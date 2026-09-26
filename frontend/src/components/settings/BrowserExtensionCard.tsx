"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, MonitorSmartphone, Puzzle, Unplug } from "lucide-react";
import { toast } from "sonner";

import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { apiClient, getApiErrorMessage } from "@/lib/api";
import { detectExtension, pairExtension } from "@/lib/extension-bridge";

type Device = {
  id: string;
  name: string;
  created_at: string | null;
  last_seen_at: string | null;
};

type Pairing = { device_id: string; name: string; token: string };

function browserName(): string {
  const ua = navigator.userAgent;
  const browser = /Edg\//.test(ua) ? "Edge" : /Brave/.test(ua) ? "Brave" : /Chrome\//.test(ua) ? "Chrome" : "Browser";
  const os = /Mac OS X/.test(ua) ? "macOS" : /Windows/.test(ua) ? "Windows" : /Linux/.test(ua) ? "Linux" : "";
  return os ? `${browser} on ${os}` : browser;
}

function lastSeen(value: string | null): string {
  if (!value) return "Never connected";
  const minutes = Math.round((Date.now() - new Date(value).getTime()) / 60_000);
  if (minutes < 2) return "Active now";
  if (minutes < 60) return `Seen ${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `Seen ${hours} h ago`;
  return `Seen ${new Date(value).toLocaleDateString()}`;
}

export function BrowserExtensionCard() {
  const queryClient = useQueryClient();
  const [installedVersion, setInstalledVersion] = useState<string | null | undefined>(undefined);
  const [code, setCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    detectExtension().then(setInstalledVersion);
  }, []);

  const devices = useQuery<{ devices: Device[] }>({
    queryKey: ["extension-devices"],
    queryFn: async () => (await apiClient.get("/extension/devices")).data,
    refetchInterval: 30_000,
  });

  const pair = useMutation({
    mutationFn: async () => (await apiClient.post<Pairing>("/extension/pair", { name: browserName() })).data,
    onSuccess: async (pairing) => {
      const connected = installedVersion ? await pairExtension(pairing.token) : false;
      if (connected) {
        setCode(null);
        toast.success("This browser is connected. Applications will open here for your review.");
      } else {
        // Shown once: the server keeps only a hash of it.
        setCode(pairing.token);
      }
      queryClient.invalidateQueries({ queryKey: ["extension-devices"] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Could not create a connection code")),
  });

  const revoke = useMutation({
    mutationFn: async (id: string) => apiClient.delete(`/extension/devices/${id}`),
    onSuccess: () => {
      toast.success("Browser disconnected");
      queryClient.invalidateQueries({ queryKey: ["extension-devices"] });
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Could not disconnect that browser")),
  });

  async function copyCode() {
    if (!code) return;
    await navigator.clipboard.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  const list = devices.data?.devices ?? [];

  return (
    <section className="rounded-2xl border border-border bg-card/60 p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 font-medium">
            <Puzzle className="h-4 w-4 shrink-0 text-primary" /> Browser extension
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Apply from your own browser, where you are already signed in to LinkedIn and Naukri. The extension
            fills each application and waits — nothing is submitted until you press Submit in its review panel.
          </p>
          <p className="mt-2 text-xs text-muted-foreground" aria-live="polite">
            {installedVersion === undefined
              ? "Checking this browser…"
              : installedVersion
                ? `Extension installed in this browser (v${installedVersion}).`
                : "Extension not detected in this browser. Load extension/ from the CareerCraft repository (chrome://extensions → Developer mode → Load unpacked), or connect it with a code."}
          </p>
        </div>
        <LiquidGlassButton
          tone="primary"
          size="sm"
          className="shrink-0"
          disabled={pair.isPending}
          onClick={() => pair.mutate()}
        >
          <MonitorSmartphone className="mr-2 h-4 w-4" />
          {pair.isPending ? "Connecting…" : installedVersion ? "Connect this browser" : "Get a connection code"}
        </LiquidGlassButton>
      </div>

      {code ? (
        <div className="mt-4 rounded-xl border border-warning/40 bg-warning/10 p-4">
          <p className="text-sm font-medium">Paste this code in the extension popup</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Open the CareerCraft extension, enter {typeof window !== "undefined" ? window.location.origin : "this site"} as the
            URL and this code. It is shown only once.
          </p>
          <div className="mt-3 flex min-w-0 items-center gap-2">
            <code className="min-w-0 flex-1 truncate rounded-lg border border-border bg-background px-3 py-2 text-xs">
              {code}
            </code>
            <LiquidGlassButton tone="ghost" size="sm" className="shrink-0" onClick={copyCode}>
              {copied ? <Check className="mr-2 h-4 w-4" /> : <Copy className="mr-2 h-4 w-4" />}
              {copied ? "Copied" : "Copy"}
            </LiquidGlassButton>
          </div>
        </div>
      ) : null}

      <div className="mt-5">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Connected browsers</p>
        {devices.isError ? (
          <p role="alert" className="mt-2 text-sm text-danger">Could not load connected browsers.</p>
        ) : list.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">No browser connected yet.</p>
        ) : (
          <ul className="mt-2 divide-y divide-border rounded-xl border border-border">
            {list.map((device) => (
              <li key={device.id} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{device.name}</p>
                  <p className="text-xs text-muted-foreground">{lastSeen(device.last_seen_at)}</p>
                </div>
                <LiquidGlassButton
                  tone="ghost"
                  size="sm"
                  className="shrink-0"
                  disabled={revoke.isPending}
                  onClick={() => {
                    if (window.confirm(`Disconnect ${device.name}? It will stop receiving applications.`)) {
                      revoke.mutate(device.id);
                    }
                  }}
                >
                  <Unplug className="mr-2 h-4 w-4" /> Disconnect
                </LiquidGlassButton>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
