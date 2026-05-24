"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

const PROVIDERS = [
  {
    value: "anthropic",
    label: "Anthropic (Claude)",
    defaultModel: "claude-sonnet-4-6",
  },
  { value: "openai", label: "OpenAI (GPT)", defaultModel: "gpt-4o" },
  {
    value: "google",
    label: "Google (Gemini)",
    defaultModel: "gemini-2.0-flash",
  },
  { value: "ollama", label: "Ollama (Local)", defaultModel: "llama3.2" },
  {
    value: "nvidia_nim",
    label: "NVIDIA NIM",
    defaultModel: "meta/llama-3.1-70b-instruct",
  },
] as const;

interface ModelSetting {
  id: string;
  provider: string;
  model_name: string | null;
  is_active: boolean;
}

export default function ModelSettingsPage() {
  const qc = useQueryClient();
  const [provider, setProvider] = useState("anthropic");
  const [apiKey, setApiKey] = useState("");
  const [modelName, setModelName] = useState("claude-sonnet-4-6");
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");

  const { data: models = [] } = useQuery<ModelSetting[]>({
    queryKey: ["models"],
    queryFn: () =>
      apiClient
        .get("/api/v1/users/me/models")
        .then((r) => r.data as ModelSetting[]),
  });

  const { mutate: add, isPending } = useMutation({
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

  return (
    <main className="p-8 max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold">AI Model Settings</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Add Model</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Select
            value={provider}
            onValueChange={(v) => {
              setProvider(v);
              const found = PROVIDERS.find((p) => p.value === v);
              setModelName(found?.defaultModel ?? "");
            }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PROVIDERS.map((p) => (
                <SelectItem key={p.value} value={p.value}>
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            placeholder="Model name"
          />
          <Input
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={
              provider === "ollama" ? "No API key required" : "API Key"
            }
            type="password"
            disabled={provider === "ollama"}
          />
          {provider === "ollama" && (
            <Input
              value={ollamaUrl}
              onChange={(e) => setOllamaUrl(e.target.value)}
              placeholder="Ollama URL"
            />
          )}
          <Button
            onClick={() => add()}
            disabled={isPending || (!apiKey && provider !== "ollama")}
          >
            {isPending ? "Adding..." : "Add Model"}
          </Button>
        </CardContent>
      </Card>
      <div className="space-y-2">
        <h2 className="font-medium">Configured Models</h2>
        {models.map((m) => (
          <div
            key={m.id}
            className="flex items-center justify-between border rounded p-3"
          >
            <div>
              <span className="font-medium text-sm">{m.provider}</span>
              <span className="text-slate-500 text-sm ml-2">{m.model_name}</span>
            </div>
            {m.is_active && <Badge>Active</Badge>}
          </div>
        ))}
      </div>
    </main>
  );
}
