"use client";

import { usePathname } from "next/navigation";
import { ImmersiveCanvas } from "@/components/immersive/ImmersiveCanvas";

type SceneKind = "hero" | "dashboard" | "jobs" | "agents" | "resume" | "interview" | "ambient";

function sceneFromPath(pathname: string): SceneKind {
  if (pathname.startsWith("/dashboard")) return "dashboard";
  if (pathname.startsWith("/jobs")) return "jobs";
  if (pathname.startsWith("/agents")) return "agents";
  if (pathname.startsWith("/resume")) return "resume";
  if (pathname.startsWith("/interview")) return "interview";
  return "ambient";
}

export function AppImmersiveStage() {
  const pathname = usePathname();
  return <ImmersiveCanvas kind={sceneFromPath(pathname)} />;
}
