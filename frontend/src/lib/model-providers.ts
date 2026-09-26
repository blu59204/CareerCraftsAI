// The bring-your-own-model catalog shared by onboarding and Settings → AI Models.
// `value` must match a provider handled by backend/app/core/model_router.py.

export const PROVIDERS = [
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
    value: "deepseek",
    label: "DeepSeek",
    models: ["deepseek-flash", "deepseek-v4-pro"],
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

export type Provider = (typeof PROVIDERS)[number]["value"];

export const PROVIDER_MODELS = Object.fromEntries(
  PROVIDERS.map((p) => [p.value, p.models]),
) as unknown as Record<Provider, readonly string[]>;
