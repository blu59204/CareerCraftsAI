"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Notebook, Trash } from "@phosphor-icons/react";
import { apiClient } from "@/lib/api";
import { SettingsNav } from "@/components/settings/SettingsNav";
import {
  Bezel,
  EmptyPanel,
  IconButton,
  IslandButton,
  PageHero,
  PanelTitle,
  Reveal,
  Screen,
  Skeleton,
} from "@/components/vanguard";

type Kind = "learnings" | "preferences" | "procedures" | "episodes";

interface MemoryItem {
  id: number;
  text: string | null;
  label?: string | null;
  agent_type?: string | null;
  task_type?: string | null;
  created_at: string;
}

type MemoryResponse = Record<Kind, MemoryItem[]>;

const SECTIONS: ReadonlyArray<{ kind: Kind; title: string; hint: string }> = [
  { kind: "preferences", title: "Preferences", hint: "Choices the agents learned from how you edit and approve." },
  { kind: "learnings", title: "What worked", hint: "Patterns the agents found that got better results for you." },
  { kind: "procedures", title: "Routines", hint: "Multi-step approaches the agents reuse." },
  { kind: "episodes", title: "Recent runs", hint: "Short summaries of past agent runs." },
];

export default function MemoryPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<MemoryResponse>({
    queryKey: ["agent-memory"],
    queryFn: () => apiClient.get("/memory").then((r) => r.data as MemoryResponse),
  });

  const { mutate: forgetOne } = useMutation({
    mutationFn: ({ kind, id }: { kind: Kind; id: number }) => apiClient.delete(`/memory/${kind}/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agent-memory"] }),
    onError: () => toast.error("Could not forget that. Try again."),
  });

  const { mutate: forgetAll, isPending: forgettingAll } = useMutation({
    mutationFn: () => apiClient.delete("/memory"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agent-memory"] });
      toast.success("CareerCraft has forgotten everything it learned about you.");
    },
    onError: () => toast.error("Could not clear memory. Try again."),
  });

  const total = data ? SECTIONS.reduce((sum, s) => sum + data[s.kind].length, 0) : 0;

  return (
    <Screen>
      <div className="space-y-6 md:space-y-8">
        <PageHero
          className="pb-4 md:pb-6"
          eyebrow="Memory"
          title="What CareerCraft remembers"
          accent="You decide what stays."
          description="Agents keep short notes about what works for you so each run starts smarter. Delete any note, or clear them all."
          actions={
            total > 0 ? (
              <IslandButton
                tone="ghost"
                disabled={forgettingAll}
                onClick={() => {
                  if (window.confirm("Forget everything the agents have learned about you?")) forgetAll();
                }}
              >
                Forget everything
              </IslandButton>
            ) : undefined
          }
        />

        <Reveal subtle>
          <SettingsNav />
        </Reveal>

        {isLoading ? (
          <Skeleton className="h-32 w-full rounded-2xl" />
        ) : total === 0 ? (
          <Bezel tone="muted">
            <EmptyPanel
              compact
              icon={<Notebook size={22} weight="light" />}
              title="Nothing remembered yet"
              description="As agents run, what they learn about your preferences shows up here."
            />
          </Bezel>
        ) : (
          SECTIONS.filter((s) => (data?.[s.kind].length ?? 0) > 0).map((section) => (
            <Reveal key={section.kind}>
              <Bezel coreClassName="p-6">
                <PanelTitle icon={<Notebook size={16} weight="light" />} title={section.title} />
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{section.hint}</p>
                <ul className="mt-4 divide-y divide-border">
                  {data![section.kind].map((item) => (
                    <li key={item.id} className="flex items-start justify-between gap-3 py-3">
                      <div className="min-w-0 text-sm leading-6">
                        {item.label ? <span className="font-medium text-foreground">{item.label}: </span> : null}
                        <span className="text-foreground">{item.text ?? item.task_type ?? "(empty)"}</span>
                        <div className="text-xs text-muted-foreground">
                          {[item.agent_type, new Date(item.created_at).toLocaleDateString()].filter(Boolean).join(" · ")}
                        </div>
                      </div>
                      <IconButton
                        size="sm"
                        aria-label="Forget this"
                        onClick={() => forgetOne({ kind: section.kind, id: item.id })}
                      >
                        <Trash size={16} weight="light" />
                      </IconButton>
                    </li>
                  ))}
                </ul>
              </Bezel>
            </Reveal>
          ))
        )}
      </div>
    </Screen>
  );
}
