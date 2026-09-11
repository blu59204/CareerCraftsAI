"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle, XCircle, Loader2, Trash2, Zap } from "lucide-react";
import { apiClient } from "@/lib/api";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { CommandHeader } from "@/components/immersive/CommandHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { useTheme } from "@/components/theme/ThemeProvider";
import { cn } from "@/lib/utils";

const PROVIDERS = [
  {
    value: "anthropic",
    label: "Anthropic (Claude)",
    models: [
      "claude-opus-4-8",
      "claude-opus-4-7",
      "claude-opus-4-6",
      "claude-opus-4-5",
      "claude-sonnet-4-6",
      "claude-sonnet-4-5",
      "claude-haiku-4-5",
    ],
  },
  {
    value: "openai",
    label: "OpenAI (GPT)",
    models: [
      "gpt-5.5",
      "gpt-5.4",
      "gpt-5.4-mini",
      "gpt-5.4-nano",
      "gpt-5.2",
      "gpt-5.1-codex",
      "gpt-4o",
      "gpt-4o-mini",
    ],
  },
  {
    value: "google",
    label: "Google (Gemini)",
    models: [
      "gemini-3.1-pro-preview",
      "gemini-3-pro",
      "gemini-3.5-flash",
      "gemini-3.1-flash-lite",
      "gemini-2.5-pro",
      "gemini-2.5-flash",
      "gemini-2.5-flash-lite",
    ],
  },
  {
    value: "ollama",
    label: "Ollama (Local)",
    models: ["llama3.3", "llama3.2", "llama3.1", "qwen2.5", "mistral", "phi3"],
  },
  {
    value: "nvidia_nim",
    label: "NVIDIA NIM",
    models: [
      "meta/llama-3.3-70b-instruct",
      "meta/llama-3.1-405b-instruct",
      "meta/llama-3.1-70b-instruct",
      "meta/llama-3.1-8b-instruct",
      "nvidia/llama-3.3-nemotron-super-49b-v1.5",
      "deepseek-ai/deepseek-v3.2",
      "deepseek-ai/deepseek-r1",
      "qwen/qwq-32b",
      // Vision (image input) — needed for screenshot-based browser control
      "moonshotai/kimi-k2.6",
      "meta/llama-4-maverick-17b-128e-instruct",
      "meta/llama-3.2-90b-vision-instruct",
      "meta/llama-3.2-11b-vision-instruct",
      "nvidia/nemotron-nano-12b-v2-vl",
      "nvidia/llama-3.1-nemotron-nano-vl-8b-v1",
      "nvidia/vila",
      "google/gemma-3-12b-it",
      "google/gemma-3-4b-it",
      "microsoft/phi-3-vision-128k-instruct",
    ],
  },
  {
    value: "openrouter",
    label: "OpenRouter (100+ models via one key)",
    models: [
      // Moonshot
      "moonshotai/kimi-k2.6",
      // Anthropic
      "anthropic/claude-3.5-sonnet",
      "anthropic/claude-3-opus",
      "anthropic/claude-3-haiku",
      // OpenAI
      "openai/gpt-4o",
      "openai/gpt-4o-mini",
      "openai/o1-preview",
      // Google
      "google/gemini-pro-1.5",
      "google/gemini-flash-1.5",
      // Meta
      "meta-llama/llama-3.1-405b-instruct",
      "meta-llama/llama-3.1-70b-instruct",
      // DeepSeek
      "deepseek/deepseek-chat",
      "deepseek/deepseek-reasoner",
      // MiniMax (recommended by OpenCode for code + tool use)
      "minimax/minimax-m2",
    ],
  },
  {
    value: "opencode",
    label: "OpenCode Zen (50+ models, 1 key)",
    models: [
      // GPT family
      "gpt-5.5",
      "gpt-5.5-pro",
      "gpt-5.4",
      "gpt-5.4-pro",
      "gpt-5.4-mini",
      "gpt-5.4-nano",
      "gpt-5.3-codex",
      "gpt-5.3-codex-spark",
      "gpt-5.2",
      "gpt-5.2-codex",
      "gpt-5.1",
      "gpt-5.1-codex",
      "gpt-5.1-codex-max",
      "gpt-5.1-codex-mini",
      "gpt-5",
      "gpt-5-codex",
      "gpt-5-nano",
      // Claude family
      "claude-opus-4-8",
      "claude-opus-4-7",
      "claude-opus-4-6",
      "claude-opus-4-5",
      "claude-opus-4-1",
      "claude-sonnet-4-6",
      "claude-sonnet-4-5",
      "claude-sonnet-4",
      "claude-haiku-4-5",
      "claude-3-5-haiku",
      // Gemini family
      "gemini-3.5-flash",
      "gemini-3.1-pro",
      "gemini-3-flash",
      // Qwen family
      "qwen3.7-max",
      "qwen3.7-plus",
      "qwen3.6-plus",
      "qwen3.6-plus-free",
      "qwen3.5-plus",
      // DeepSeek
      "deepseek-v4-flash",
      "deepseek-v4-flash-free",
      // MiniMax
      "minimax-m2.7",
      "minimax-m2.5",
      "minimax-m3-free",
      // GLM
      "glm-5.1",
      "glm-5",
      // Kimi
      "kimi-k2.5",
      "kimi-k2.6",
      // Other
      "grok-build-0.1",
      "big-pickle",
      "mimo-v2.5-free",
      "nemotron-3-super-free",
      "nemotron-3-ultra-free",
    ],
  },
] as const;

type Provider = (typeof PROVIDERS)[number]["value"];

const PROVIDER_MODELS = Object.fromEntries(
  PROVIDERS.map((p) => [p.value, p.models]),
) as unknown as Record<Provider, readonly string[]>;

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
  const [modelName, setModelName] = useState<string>(PROVIDER_MODELS.anthropic[0]);
  const [customMode, setCustomMode] = useState(false);
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
    onError: (err: unknown) => {
      const data = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail;
      const msg = Array.isArray(data)
        ? (data[0] as { msg?: string })?.msg ?? "Invalid input"
        : typeof data === "string"
          ? data
          : "Failed to add model";
      toast.error(msg);
    },
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
    setCustomMode(false);
    setModelName(PROVIDER_MODELS[next][0] ?? "");
  };

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      <motion.div variants={fadeUp}>
        <CommandHeader
          eyebrow="AI Automation"
          title="Model Settings"
          description="Bring your own model keys, test provider health, and keep routing explicit."
        />
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

          <label className="mt-4 block text-xs text-muted-foreground">Model</label>
          <select
            value={customMode ? "__custom__" : modelName}
            onChange={(e) => {
              const v = e.target.value;
              if (v === "__custom__") {
                setCustomMode(true);
                setModelName("");
              } else {
                setCustomMode(false);
                setModelName(v);
              }
            }}
            className="mt-1 w-full rounded-2xl border border-border bg-background p-3 text-sm"
          >
            {PROVIDER_MODELS[provider].map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
            <option value="__custom__">Custom…</option>
          </select>
          {customMode && (
            <input
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder="Type a model ID your key supports"
              autoFocus
              className="mt-2 w-full rounded-2xl border border-border bg-background p-3 text-sm"
            />
          )}

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
