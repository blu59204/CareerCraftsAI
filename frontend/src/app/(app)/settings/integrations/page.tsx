"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Link2, RefreshCw, Unplug } from "lucide-react";
import { toast } from "sonner";

import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { apiErrorMessage, apiClient } from "@/lib/api";

type Provider = "gmail" | "google_drive" | "google_calendar" | "outlook_mail" | "outlook_calendar";
type ConnectionStatus = "pending" | "connected" | "disconnected" | "error" | "revoked";

type Connection = {
  provider: Provider;
  status: ConnectionStatus;
  connected_at: string | null;
  last_synced_at: string | null;
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
  const connections = useQuery<Connection[]>({
    queryKey: ["integrations"],
    queryFn: async () => (await apiClient.get<Connection[]>("/integrations")).data,
  });

  const connect = useMutation({
    mutationFn: async (provider: Provider) => (
      await apiClient.post<ConnectSession>("/integrations/connect-session", {
        provider,
        return_path: "/settings/integrations",
      })
    ).data,
    onSuccess: (session) => {
      // Nango's hosted Connect page receives only the short-lived session link.
      window.location.assign(session.connect_link);
    },
    onError: (error) => toast.error(apiErrorMessage(error, "Could not start the connection.")),
  });

  const disconnect = useMutation({
    mutationFn: async (provider: Provider) => apiClient.delete(`/integrations/${provider}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
      toast.success("Integration disconnected");
    },
    onError: (error) => toast.error(apiErrorMessage(error, "Could not disconnect the integration.")),
  });

  const byProvider = new Map(connections.data?.map((connection) => [connection.provider, connection]));

  return (
    <main className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      <div>
        <p className="text-sm text-muted-foreground">Connected accounts</p>
        <h1 className="text-2xl font-semibold">Integrations</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Connections are confirmed by the provider before they become available.
        </p>
      </div>

      {connections.isError ? (
        <p role="alert" className="rounded-xl border border-destructive/40 p-4 text-sm text-destructive">
          Could not load integrations. Try again shortly.
        </p>
      ) : null}

      <div className="space-y-3">
        {PROVIDERS.map((provider) => {
          const connection = byProvider.get(provider.id);
          const connected = connection?.status === "connected";
          const pending = connection?.status === "pending";
          const isBusy = connect.isPending || disconnect.isPending;

          return (
            <section key={provider.id} className="flex items-center justify-between gap-4 rounded-2xl border bg-card p-5">
              <div>
                <h2 className="font-medium">{provider.name}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{provider.description}</p>
                <p className="mt-2 text-xs capitalize text-muted-foreground" aria-live="polite">
                  Status: {statusLabel(connection?.status)}
                </p>
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
                  onClick={() => connect.mutate(provider.id)}
                >
                  {pending ? <RefreshCw className="mr-2 h-4 w-4" /> : <Link2 className="mr-2 h-4 w-4" />}
                  {pending ? "Reconnect" : "Connect"}
                </LiquidGlassButton>
              )}
              {connected ? <Check className="h-5 w-5 text-success" aria-label="Connected" /> : null}
            </section>
          );
        })}
      </div>
    </main>
  );
}
