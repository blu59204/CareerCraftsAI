"use client";

import dynamic from "next/dynamic";
import { cn } from "@/lib/utils";

type SceneKind = "hero" | "dashboard" | "jobs" | "agents" | "resume" | "interview" | "ambient";

const CareerCommandScene = dynamic(
  () => import("./CareerCommandScene").then((mod) => mod.CareerCommandScene),
  {
    ssr: false,
    loading: () => <div className="immersive-fallback" />,
  },
);

export function ImmersiveCanvas({
  kind = "ambient",
  className,
}: {
  kind?: SceneKind;
  className?: string;
}) {
  return (
    <div aria-hidden className={cn("immersive-canvas", className)}>
      <CareerCommandScene kind={kind} />
      <div className="immersive-vignette" />
    </div>
  );
}
