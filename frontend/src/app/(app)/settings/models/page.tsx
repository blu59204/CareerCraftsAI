"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { EmptyState } from "@/components/ui/EmptyState";
import { useTheme } from "@/components/theme/ThemeProvider";

const PROVIDERS = [
  { value: "anthropic", label: "Anthropic (Claude)", defaultModel: "claude-sonnet-4-6" },
  { value: "openai", label: "OpenAI (GPT)", defaultModel: "gpt-4o" },
  { value: "google", label: "Google (Gemini)", defaultModel: "gemini-2.0-flash" },
  { value: "ollama", label: "Ollama (Local)", defaultModel: "llama3.2" },
  { value: "nvidia_nim", label: "NVIDIA NIM", defaultModel: "meta/llama-3.1-70b-instruct" },
] as const;

type Provider = (typeof PROVIDERS)[number]["value"];

interface ModelSetting {
  id: string;
  provider: string;
  model_name: string | null;
  is_active: boolean;
}

export default function SettingsModelsPage() {
  const { theme, toggleTheme } = useTheme();
  const qc = useQueryClient();
  const [provider, setProvider] = useState<Provider>("anthropic");
  const [apiKey, setApiKey] = useState("");
  const [modelName, setModelName] = useState("claude-sonnet-4-6");
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");

  const { data: models = [] } = useQuery<ModelSetting[]>({
    queryKey: ["models"],
    queryFn: () =>
      apiClient.get("/api/v1/users/me/models").then((r) => r.data as ModelSetting[]),
  });

  const { mutate: addModel, isPending } = useMutation({
    mutationFn: () =>
      apiClient.post("/api/v1/users/me/models", {
        provider,
        api_key: apiKey,
        model_name: modelName,
        ollama_url: provider === "ollama" ? ollamaUrl : null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["models"] });
      setApiKey("");
      toast.success("Model added");
    },
    onError: () => toast.error("Failed to add model"),
  });

  const onProviderChange = (next: Provider) => {
    setProvider(next);
    const found = PROVIDERS.find((p) => p.value === next);
    setModelName(found?.defaultModel ?? "");
  };

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      <motion.div variants={fadeUp}>
        <div className="text-sm text-muted-foreground">Settings</div>
        <h1 className="mt-1 text-3xl font-medium">Models &amp; preferences</h1>
      </motion.div>

      <motion.div variants={fadeUp} className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <section className="rounded-3xl border border-border bg-card/60 p-6">
          <div className="text-base font-medium">Add provider</div>
          <p className="mt-1 text-sm text-muted-foreground">
            BYOK — your keys are encrypted at rest. Use Ollama for free local inference.
          </p>

          <label className="mt-6 block text-xs text-muted-foreground">Provider</label>
          <select
            value={provider}
            onChange={(e) => onProviderChange(e.target.value as Provider)}
            className="mt-1 w-full rounded-2xl border border-border bg-background p-3 text-sm"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>

          <label className="mt-4 block text-xs text-muted-foreground">Model name</label>
          <input
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            placeholder="Model name"
            className="mt-1 w-full rounded-2xl border border-border bg-background p-3 text-sm"
          />

          <label className="mt-4 block text-xs text-muted-foreground">API key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={provider === "ollama" ? "No API key required" : "API key"}
            disabled={provider === "ollama"}
            className="mt-1 w-full rounded-2xl border border-border bg-background p-3 text-sm disabled:opacity-50"
          />

          {provider === "ollama" && (
            <>
              <label className="mt-4 block text-xs text-muted-foreground">Ollama URL</label>
              <input
                value={ollamaUrl}
                onChange={(e) => setOllamaUrl(e.target.value)}
                placeholder="http://localhost:11434"
                className="mt-1 w-full rounded-2xl border border-border bg-background p-3 text-sm"
              />
            </>
          )}

          <div className="mt-6">
            <LiquidGlassButton
              tone="primary"
              size="md"
              onClick={() => addModel()}
              disabled={isPending || (!apiKey && provider !== "ollama")}
            >
              {isPending ? "Adding…" : "Add model"}
            </LiquidGlassButton>
          </div>
        </section>

        <aside className="space-y-4">
          <div className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="text-base font-medium">Theme</div>
            <p className="mt-1 text-sm text-muted-foreground">
              Current: {theme}. Saved in your browser.
            </p>
            <div className="mt-4">
              <LiquidGlassButton tone="ghost" size="sm" onClick={toggleTheme}>
                Switch to {theme === "dark" ? "light" : "dark"}
              </LiquidGlassButton>
            </div>
          </div>

          <div className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="text-base font-medium">Configured models</div>
            <div className="mt-4 space-y-2">
              {models.length === 0 ? (
                <EmptyState title="No models yet" description="Add one to enable agent runs." />
              ) : (
                models.map((m) => (
                  <div
                    key={m.id}
                    className="flex items-center justify-between rounded-2xl border border-border bg-card px-4 py-3"
                  >
                    <div>
                      <div className="text-sm font-medium">{m.provider}</div>
                      <div className="text-xs text-muted-foreground">{m.model_name ?? "—"}</div>
                    </div>
                    {m.is_active && (
                      <span className="rounded-full bg-success/15 px-2 py-0.5 text-xs text-success">
                        Active
                      </span>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </aside>
      </motion.div>
    </motion.div>
  );
}
