"use client";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, getApiErrorMessage } from "@/lib/api";
import { openNangoConnectWindow } from "@/lib/nango-connect";
import { ArrowsClockwise, CircleNotch, GithubLogo } from "@phosphor-icons/react";
import { Bezel, Input, IslandButton, Notice, PanelTitle, StatusPill } from "@/components/vanguard";

type Profile = { skills: { name: string }[]; top_repos: { name: string; url: string }[]; suggested_projects: { name: string; url: string; reason: string }[] };
export function GitHubSettings({ onboarding = false }: { onboarding?: boolean }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const client = useQueryClient();
  const pollTimer = useRef<number | null>(null);
  useEffect(() => () => { if (pollTimer.current) window.clearInterval(pollTimer.current); }, []);
  const profile = useQuery<Profile | null>({ queryKey: ["github-profile"], retry: false, queryFn: async () => {
    try { return (await apiClient.get("/integrations/github/profile")).data; }
    catch (e) { if ((e as { response?: { status: number } }).response?.status === 404) return null; throw e; }
  } });
  async function refresh(path = "/integrations/github/refresh", body?: { url: string }) {
    setBusy(true); setError("");
    try { await apiClient.post(path, body); await client.invalidateQueries({ queryKey: ["github-profile"] }); }
    catch (e) { setError(getApiErrorMessage(e, "GitHub unavailable. Try a public profile URL.")); }
    finally { setBusy(false); }
  }
  async function connect() {
    const popup = openNangoConnectWindow();
    if (!popup) { setError("Allow popups to connect GitHub, or use a public profile URL."); return; }
    setBusy(true); setError("");
    try {
      const { data } = await apiClient.post("/integrations/connect-session", { provider: "github", return_path: onboarding ? "/onboarding" : "/settings/integrations" });
      if (!data.connect_link) throw new Error("GitHub OAuth is unavailable");
      popup.location.href = data.connect_link;
      if (pollTimer.current) window.clearInterval(pollTimer.current);
      pollTimer.current = window.setInterval(() => { if (popup.closed) { if (pollTimer.current) window.clearInterval(pollTimer.current); pollTimer.current = null; setBusy(false); void refresh(); } }, 1000);
    } catch (e) { popup.close(); setBusy(false); setError(getApiErrorMessage(e, "GitHub OAuth unavailable. Use a public profile URL.")); }
  }
  async function remove(disconnect: boolean) {
    setBusy(true); setError("");
    try {
      await apiClient.delete("/integrations/github/data");
      if (disconnect) { try { await apiClient.delete("/integrations/github"); } catch (e) { if ((e as { response?: { status: number } }).response?.status !== 404) setError("Profile data deleted. OAuth disconnect is unavailable; retry disconnect when the integration service returns."); } }
      await client.invalidateQueries({ queryKey: ["github-profile"] });
    } catch (e) { setError(getApiErrorMessage(e, "Could not delete GitHub data")); }
    finally { setBusy(false); }
  }
  const connected = !!profile.data;
  const spinner = <CircleNotch size={14} weight="light" className="animate-spin motion-reduce:animate-none" />;
  const body = (
      <section aria-labelledby="github-section-title" className="space-y-5">
        <PanelTitle
          icon={<GithubLogo size={16} weight="light" />}
          title={<span id="github-section-title">GitHub</span>}
          meta={
            profile.isPending ? (
              <StatusPill tone="neutral" live>Checking…</StatusPill>
            ) : (
              <StatusPill tone={connected ? "success" : "neutral"}>{connected ? "Connected" : "Optional"}</StatusPill>
            )
          }
        />
        <p className="text-sm leading-6 text-muted-foreground">
          Adds evidence from your public repositories to job matching and suggests projects to highlight. Public
          repositories only. You can skip this.
        </p>

        {!connected && (
          <>
            <div className="flex flex-wrap gap-2">
              <IslandButton
                type="button"
                tone="primary"
                size="sm"
                disabled={busy}
                onClick={() => void connect()}
                icon={busy ? spinner : <GithubLogo size={14} weight="light" />}
              >
                Connect GitHub
              </IslandButton>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void refresh("/integrations/github/public-profile", { url });
              }}
              className="space-y-2"
            >
              <label htmlFor="github-public-url" className="block pl-1 text-[12px] font-medium text-muted-foreground">
                Or use a public profile URL
              </label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  id="github-public-url"
                  type="url"
                  required
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://github.com/username"
                  trayClassName="flex-1"
                />
                <IslandButton type="submit" tone="ghost" size="md" disabled={busy}>
                  Use public profile
                </IslandButton>
              </div>
            </form>
          </>
        )}

        {(error || profile.isError) && (
          <Notice tone="danger">{error || "GitHub is unavailable. You can continue without it."}</Notice>
        )}

        {connected && profile.data && (
          <div className="space-y-4">
            <div>
              <p className="pl-1 text-[12px] font-medium text-muted-foreground">Skills from your repositories</p>
              {profile.data.skills.length ? (
                <ul className="mt-2 flex flex-wrap gap-2">
                  {profile.data.skills.map((s) => (
                    <li key={s.name}>
                      <StatusPill tone="neutral">{s.name}</StatusPill>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">No skills found yet.</p>
              )}
            </div>
            {profile.data.suggested_projects.length > 0 && (
              <ul className="space-y-2">
                {profile.data.suggested_projects.map((p) => (
                  <li key={p.url} className="rounded-2xl bg-foreground/[0.03] px-4 py-3 ring-1 ring-foreground/[0.06] dark:bg-white/[0.03] dark:ring-white/10">
                    <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-primary hover:underline">
                      {p.name}
                    </a>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">{p.reason}</p>
                  </li>
                ))}
              </ul>
            )}
            <div className="flex flex-wrap gap-2">
              <IslandButton type="button" tone="ghost" size="sm" disabled={busy} onClick={() => void refresh()} icon={busy ? spinner : <ArrowsClockwise size={14} weight="light" />}>
                Refresh
              </IslandButton>
              <IslandButton type="button" tone="quiet" size="sm" disabled={busy} onClick={() => void remove(false)}>
                Delete profile data
              </IslandButton>
              <IslandButton type="button" tone="danger" size="sm" disabled={busy} onClick={() => void remove(true)}>
                Disconnect
              </IslandButton>
            </div>
          </div>
        )}
      </section>
  );
  // Onboarding already frames each step in a card.
  return onboarding ? body : <Bezel coreClassName="p-6 md:p-7">{body}</Bezel>;
}
