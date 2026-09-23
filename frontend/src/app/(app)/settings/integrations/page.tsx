"use client";

import { useEffect, useMemo, useState } from "react";
import { useUser } from "@clerk/nextjs";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Link2, RefreshCw, Unplug } from "lucide-react";
import { toast } from "sonner";

import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { SettingsNav } from "@/components/settings/SettingsNav";
import { apiClient } from "@/lib/api";
import { openNangoConnectWindow } from "@/lib/nango-connect";

type Provider = "gmail" | "google_drive" | "google_calendar" | "outlook_mail" | "outlook_calendar";
type ConnectionStatus = "pending" | "connected" | "disconnected" | "error" | "revoked";

type Connection = {
  provider: Provider;
  status: ConnectionStatus;
  connected_at: string | null;
  last_synced_at: string | null;
  account_email: string | null;
};

type ConnectSession = {
  provider: Provider;
  connect_link: string;
  expires_at: string | null;
};

const PROVIDERS: Array<{ id: Provider; name: string; description: string }> = [
  { id: "gmail", name: "Gmail", description: "Read context and send approved outreach." },
  { id: "google_drive", name: "Google Drive", description: "Save documents you explicitly export." },
  { id: "google_calendar", name: "Google Calendar", description: "Schedule approved interview events." },
  { id: "outlook_mail", name: "Microsoft Outlook Mail", description: "Read context and send approved outreach." },
  { id: "outlook_calendar", name: "Microsoft Outlook Calendar", description: "Schedule approved interview events." },
];

function statusLabel(status: ConnectionStatus | undefined): string {
  return status ? status.replace("-", " ") : "disconnected";
}

export default function IntegrationsSettingsPage() {
  const queryClient = useQueryClient();
  const { user: authUser } = useUser();
  const [connectingProvider, setConnectingProvider] = useState<Provider | null>(null);
  const [connectWindow, setConnectWindow] = useState<Window | null>(null);
  const connections = useQuery<Connection[]>({
    queryKey: ["integrations"],
    queryFn: async () => (await apiClient.get<Connection[]>("/integrations")).data,
    refetchInterval: connectingProvider ? 2_000 : false,
  });
  const loginEmail = authUser?.primaryEmailAddress?.emailAddress ?? null;
  const enforceGmailMatch = loginEmail?.toLowerCase().endsWith("@gmail.com") ?? false;

  const connect = useMutation({
    mutationFn: async ({ provider }: { provider: Provider; popup: Window }) => (
      await apiClient.post<ConnectSession>("/integrations/connect-session", {
        provider,
        return_path: "/settings/integrations",
      })
    ).data,
    onSuccess: (session, { provider, popup }) => {
      popup.location.href = session.connect_link;
      setConnectingProvider(provider);
      setConnectWindow(popup);
    },
    onError: () => toast.error("Could not start the connection."),
  });

  const disconnect = useMutation({
    mutationFn: async (provider: Provider) => apiClient.delete(`/integrations/${provider}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      toast.success("Integration disconnected");
    },
    onError: () => toast.error("Could not disconnect the integration."),
  });

  const byProvider = useMemo(
    () => new Map(connections.data?.map((connection) => [connection.provider, connection])),
    [connections.data],
  );
  const connectedCount = [...byProvider.values()].filter((connection) => connection.status === "connected").length;

  useEffect(() => {
    if (!connectingProvider) return;
    if (byProvider.get(connectingProvider)?.status === "connected") {
      connectWindow?.close();
      setConnectingProvider(null);
      setConnectWindow(null);
      toast.success("Integration connected");
      return;
    }
    const pendingConnection = byProvider.get(connectingProvider);
    if (
      pendingConnection?.status === "revoked" &&
      enforceGmailMatch &&
      pendingConnection.account_email &&
      loginEmail &&
      pendingConnection.account_email.toLowerCase() !== loginEmail.toLowerCase()
    ) {
      connectWindow?.close();
      setConnectingProvider(null);
      setConnectWindow(null);
      toast.error("Gmail accounts must match your @gmail.com sign-in address.");
      return;
    }
    const timer = window.setInterval(() => {
      if (connectWindow?.closed) {
        setConnectingProvider(null);
        setConnectWindow(null);
        queryClient.invalidateQueries({ queryKey: ["integrations"] });
      }
    }, 500);
    return () => window.clearInterval(timer);
  }, [byProvider, connectWindow, connectingProvider, enforceGmailMatch, loginEmail, queryClient]);

  const startConnect = (provider: Provider) => {
    const popup = openNangoConnectWindow();
    if (!popup) {
      toast.error("Please allow popups to connect an integration.");
      return;
    }
    connect.mutate({ provider, popup });
  };

  return (
    <main className="mx-auto w-full max-w-6xl space-y-7 px-4 py-8 sm:px-6">
      <header className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm text-muted-foreground">Settings / Connected accounts</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Integrations</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Connect the services CareerCraft can use for approved email, calendar, and document actions.
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card/50 px-4 py-3 text-sm">
          <span className="font-medium">{connectedCount}</span>
          <span className="ml-1 text-muted-foreground">of {PROVIDERS.length} connected</span>
        </div>
      </header>

      <SettingsNav />

      {connections.isError ? (
        <p role="alert" className="rounded-xl border border-destructive/40 p-4 text-sm text-destructive">
          Could not load integrations. Try again shortly.
        </p>
      ) : null}

      {enforceGmailMatch ? (
        <p className="rounded-xl border border-border bg-card/40 px-4 py-3 text-sm text-muted-foreground">
          Gmail must use the same <span className="font-medium text-foreground">{loginEmail}</span> address as your CareerCraft sign-in.
        </p>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        {PROVIDERS.map((provider) => {
          const connection = byProvider.get(provider.id);
          const connected = connection?.status === "connected";
          const pending = connection?.status === "pending";
          const isBusy = connect.isPending || disconnect.isPending;
          const accountMismatch = Boolean(
              provider.id === "gmail" &&
              enforceGmailMatch &&
              connection?.account_email &&
              loginEmail &&
              connection.account_email.toLowerCase() !== loginEmail.toLowerCase(),
          );

          return (
            <section key={provider.id} className="flex min-h-44 flex-col justify-between gap-5 rounded-2xl border border-border bg-card/60 p-5 transition-colors hover:border-primary/30">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-medium">{provider.name}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{provider.description}</p>
                <p className="mt-2 text-xs capitalize text-muted-foreground" aria-live="polite">
                  Status: {statusLabel(connection?.status)}
                </p>
                {connection?.account_email ? (
                  <p className="mt-1 text-xs text-muted-foreground">Connected account: {connection.account_email}</p>
                ) : null}
                {accountMismatch ? (
                  <p role="alert" className="mt-1 text-xs text-amber-600 dark:text-amber-400">
                    This Google account does not match your sign-in email ({loginEmail}). It has been disconnected; connect the matching account.
                  </p>
                ) : null}
                </div>
                {connected ? <Check className="mt-1 h-5 w-5 shrink-0 text-success" aria-label="Connected" /> : null}
              </div>
              {connected ? (
                <LiquidGlassButton
                  tone="ghost"
                  size="sm"
                  disabled={isBusy}
                  onClick={() => {
                    if (window.confirm(`Disconnect ${provider.name}?`)) disconnect.mutate(provider.id);
                  }}
                >
                  <Unplug className="mr-2 h-4 w-4" /> Disconnect
                </LiquidGlassButton>
              ) : (
                <LiquidGlassButton
                  tone={pending ? "ghost" : "primary"}
                  size="sm"
                  disabled={isBusy}
                  onClick={() => startConnect(provider.id)}
                >
                  {pending ? <RefreshCw className="mr-2 h-4 w-4" /> : <Link2 className="mr-2 h-4 w-4" />}
                  {pending ? "Reconnect" : "Connect"}
                </LiquidGlassButton>
              )}
            </section>
          );
        })}
      </div>
    </main>
  );
}
