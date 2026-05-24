"use client";

import { useState } from "react";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { OnboardingStepper } from "@/components/onboarding/OnboardingStepper";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";

function StepWrapper({ children, onNext, onPrev, canPrev, isLast }: {
  children: React.ReactNode;
  onNext: () => void;
  onPrev: () => void;
  canPrev: boolean;
  isLast: boolean;
}) {
  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-border bg-card/60 p-6">{children}</div>
      <div className="flex items-center justify-between">
        <LiquidGlassButton tone="ghost" size="sm" onClick={onPrev} disabled={!canPrev}>Back</LiquidGlassButton>
        <LiquidGlassButton tone="primary" size="sm" onClick={onNext}>{isLast ? "Finish" : "Continue"}</LiquidGlassButton>
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  const [i, setI] = useState(0);

  const next = () => setI((n) => Math.min(n + 1, 5));
  const prev = () => setI((n) => Math.max(n - 1, 0));
  const isLast = i === 5;

  const wrap = (node: React.ReactNode) => (
    <StepWrapper onNext={next} onPrev={prev} canPrev={i > 0} isLast={isLast}>{node}</StepWrapper>
  );

  const steps = [
    { id: "welcome", title: "Welcome to CareerCraft AI.", content: wrap(<p className="text-sm text-muted-foreground">Let&apos;s set up your job search in under two minutes.</p>) },
    { id: "goal", title: "What’s your goal?", content: wrap(<select className="w-full rounded-2xl border border-border bg-background p-3 text-sm"><option>First job after college</option><option>Switch roles</option><option>Internship</option></select>) },
    { id: "resume", title: "Upload your resume", content: wrap(<input type="file" accept=".pdf,.docx" className="w-full rounded-2xl border border-dashed border-border bg-background p-4 text-sm" />) },
    { id: "role", title: "Target role", content: wrap(<input placeholder="e.g. Frontend Engineer" className="w-full rounded-2xl border border-border bg-background p-3 text-sm" />) },
    { id: "locations", title: "Preferred locations", content: wrap(<input placeholder="Bangalore, Remote, Hyderabad" className="w-full rounded-2xl border border-border bg-background p-3 text-sm" />) },
    { id: "model", title: "Bring your own model", content: wrap(<div className="space-y-3 text-sm"><label className="block">Provider <select className="mt-1 w-full rounded-2xl border border-border bg-background p-3"><option>Anthropic</option><option>OpenAI</option><option>Gemini</option><option>Groq</option><option>Ollama</option></select></label><label className="block">API key <input type="password" className="mt-1 w-full rounded-2xl border border-border bg-background p-3" /></label></div>) },
  ];

  return (
    <ThemeProvider zoneDefault="light">
      <div className="min-h-screen bg-background px-6 py-16">
        <OnboardingStepper steps={steps} currentIndex={i} onChange={setI} />
      </div>
    </ThemeProvider>
  );
}
