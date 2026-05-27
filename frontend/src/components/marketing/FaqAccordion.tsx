"use client";

import * as Accordion from "@radix-ui/react-accordion";
import { ChevronDown } from "lucide-react";

const FAQ: { q: string; a: string }[] = [
  {
    q: "Do I need my own API keys?",
    a: "Yes. CareerCraft is BYOK — you bring OpenAI, Anthropic, Gemini, Groq, or a local Ollama. Your keys are encrypted at rest.",
  },
  {
    q: "Will you apply to jobs without my approval?",
    a: "No. Every email and application requires explicit approval in the UI. There is no autopilot for outbound actions.",
  },
  {
    q: "Does it work with LinkedIn?",
    a: "Yes. Browser automation runs with human-like delays. You'll see every action before it submits.",
  },
  {
    q: "How is my data stored?",
    a: "Resumes are stored as pgvector embeddings tied to your user ID. API keys are AES-256 encrypted. You can delete everything at any time.",
  },
];

export function FaqAccordion() {
  return (
    <Accordion.Root type="single" collapsible className="mx-auto max-w-3xl divide-y divide-border rounded-3xl border border-border bg-card">
      {FAQ.map((item, i) => (
        <Accordion.Item key={i} value={`q${i}`}>
          <Accordion.Header>
            <Accordion.Trigger className="group flex w-full items-center justify-between px-6 py-5 text-left text-base font-medium">
              {item.q}
              <ChevronDown className="h-4 w-4 transition-transform group-data-[state=open]:rotate-180" />
            </Accordion.Trigger>
          </Accordion.Header>
          <Accordion.Content className="px-6 pb-5 text-sm text-muted-foreground">
            {item.a}
          </Accordion.Content>
        </Accordion.Item>
      ))}
    </Accordion.Root>
  );
}
