"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle, XCircle, Loader2, Trash2, Zap } from "lucide-react";
import { apiClient } from "@/lib/api";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { EmptyState } from "@/components/ui/EmptyState";
import { useTheme } from "@/components/theme/ThemeProvider";
import { cn } from "@/lib/utils";

const PROVIDERS = [
  { value: "anthropic", label: "Anthropic (Claude)", defaultModel: "claude-sonnet-4-5" },
  { value: "openai", label: "OpenAI (GPT)", defaultModel: "gpt-4o" },
  { value: "google", label: "Google (Gemini)", defaultModel: "gemini-2.0-flash-lite" },
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
  const [modelName, setModelName] = useState("claude-sonnet-4-5");
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, "ok" | "fail">>({});

  const { data: models = [] } = useQuery<ModelSetting[]>({
    queryKey: ["models"],
    queryFn: () => apiClient.get("/users/me/models").then((r) => r.data as ModelSetting[]),
  });

  const { mutate: addModel, isPending } = useMutation({
    mutationFn: () =>
      apiClient.post("/users/me/models", {
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

  const { mutate: activateModel } = useMutation({
    mutationFn: (id: string) => apiClient.patch(`/users/me/models/${id}/activate`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["models"] });
      toast.success("Model activated");
    },
    onError: () => toast.error("Failed to activate model"),
  });

  const { mutate: deleteModel } = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/users/me/models/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["models"] });
      toast.success("Model removed");
    },
    onError: () => toast.error("Failed to remove model"),
  });

  const testModel = async (modelId: string) => {
    setTestingId(modelId);
    try {
      const { data } = await apiClient.post("/users/me/models/test", { model_id: modelId });
      setTestResults((r) => ({ ...r, [modelId]: "ok" }));
      toast.success(`Model working: ${(data as { response: string }).response}`);
    } catch (err: unknown) {
      setTestResults((r) => ({ ...r, [modelId]: "fail" }));
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Test failed";
      toast.error(detail);
    } finally {
      setTestingId(null);
    }
  };

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

      <motion.div variants={fadeUp} className="grid gap-6 lg:grid-cols-[1fr_420px]">
        {/* Add provider form */}
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

          <div className="mt-6 flex items-center gap-3">
            <LiquidGlassButton
              tone="primary"
              size="md"
              onClick={() => addModel()}
              disabled={isPending || (!apiKey && provider !== "ollama")}
            >
              {isPending ? "Saving…" : "Save API key"}
            </LiquidGlassButton>
            {!isPending && apiKey && (
              <span className="text-xs text-muted-foreground">
                Key encrypted before storage.
              </span>
            )}
          </div>
        </section>

        {/* Right column */}
        <aside className="space-y-4">
          {/* Theme */}
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

          {/* Configured models */}
          <div className="rounded-3xl border border-border bg-card/60 p-6">
            <div className="text-base font-medium">Configured models</div>
            <p className="mt-1 text-sm text-muted-foreground">
              One active model used by all agents. Test before activating.
            </p>
            <div className="mt-4 space-y-2">
              {models.length === 0 ? (
                <EmptyState title="No models yet" description="Add one to enable agent runs." />
              ) : (
                models.map((m) => {
                  const testResult = testResults[m.id];
                  const isTesting = testingId === m.id;
                  return (
                    <div
                      key={m.id}
                      className={cn(
                        "rounded-2xl border bg-card px-4 py-3 transition-colors",
                        m.is_active
                          ? "border-primary/50 bg-primary/5"
                          : "border-border",
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <div className="text-sm font-medium truncate">{m.provider}</div>
                            {m.is_active && (
                              <span className="shrink-0 rounded-full bg-success/15 px-2 py-0.5 text-xs text-success">
                                Active
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-muted-foreground truncate">
                            {m.model_name ?? "—"}
                          </div>
                        </div>
                        {/* Test result indicator */}
                        {testResult === "ok" && (
                          <CheckCircle className="h-4 w-4 shrink-0 text-success mt-0.5" />
                        )}
                        {testResult === "fail" && (
                          <XCircle className="h-4 w-4 shrink-0 text-destructive mt-0.5" />
                        )}
                      </div>

                      {/* Actions */}
                      <div className="mt-3 flex items-center gap-2">
                        {/* Test */}
                        <button
                          onClick={() => testModel(m.id)}
                          disabled={isTesting}
                          className="flex items-center gap-1 rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-medium hover:bg-muted transition-colors disabled:opacity-50"
                        >
                          {isTesting ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Zap className="h-3 w-3" />
                          )}
                          {isTesting ? "Testing…" : "Test"}
                        </button>

                        {/* Activate */}
                        {!m.is_active && (
                          <button
                            onClick={() => activateModel(m.id)}
                            className="flex items-center gap-1 rounded-xl border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/20 transition-colors"
                          >
                            Set active
                          </button>
                        )}

                        {/* Delete */}
                        <button
                          onClick={() => {
                            if (confirm(`Remove ${m.provider} / ${m.model_name ?? "model"}?`)) {
                              deleteModel(m.id);
                            }
                          }}
                          className="ml-auto flex items-center gap-1 rounded-xl border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:border-destructive hover:text-destructive transition-colors"
                        >
                          <Trash2 className="h-3 w-3" />
                          Delete
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </aside>
      </motion.div>
    </motion.div>
  );
}
