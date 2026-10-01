"use client";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, getApiErrorMessage } from "@/lib/api";
import { openNangoConnectWindow } from "@/lib/nango-connect";

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
  return <section aria-labelledby="github-section-title" className="rounded-2xl border border-border bg-card p-6 space-y-4">
    <h2 id="github-section-title" className="text-xl font-semibold">GitHub · optional</h2>
    <p className="text-sm text-muted-foreground">Add evidence from public repositories to job matching and review project suggestions. Public access only; private repositories are excluded. You can continue without connecting.</p>
    {profile.isPending && <p role="status">Loading GitHub connection…</p>}
    {!profile.data && !profile.isPending && <p>GitHub is not connected.</p>}
    <div className="flex flex-wrap gap-2">
      <button type="button" disabled={busy} onClick={() => void connect()} className="rounded-lg border border-border p-2">Connect with Nango</button>
      <button type="button" disabled={busy} onClick={() => void refresh()} className="rounded-lg border border-border p-2">Refresh profile</button>
    </div>
    <form onSubmit={e => { e.preventDefault(); void refresh("/integrations/github/public-profile", { url }); }} className="flex flex-wrap gap-2">
      <label className="grid gap-1 text-sm">Public profile URL<input type="url" required value={url} onChange={e => setUrl(e.target.value)} placeholder="https://github.com/username" className="rounded-lg border border-border bg-background p-2" /></label>
      <button disabled={busy} className="self-end rounded-lg border border-border p-2">Use public profile</button>
    </form>
    {(error || profile.isError) && <p role="alert">{error || "GitHub is unavailable. You can continue without it."}</p>}
    {busy && <p role="status">Updating GitHub…</p>}
    {profile.data && <>
      <p className="text-sm">Repository evidence: {profile.data.skills.map(s => s.name).join(", ") || "No skills found"}</p>
      <ul className="space-y-2">{profile.data.suggested_projects.map(p => <li key={p.url}><a href={p.url} target="_blank" rel="noopener noreferrer" className="underline">{p.name}</a><p className="text-sm text-muted-foreground">{p.reason}</p></li>)}</ul>
      <div className="flex gap-2"><button disabled={busy} onClick={() => void remove(true)} className="rounded-lg border p-2">Disconnect</button><button disabled={busy} onClick={() => void remove(false)} className="rounded-lg border p-2">Delete profile data</button></div>
    </>}
  </section>;
}
