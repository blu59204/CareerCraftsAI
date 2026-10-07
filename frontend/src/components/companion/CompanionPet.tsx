"use client";
import Image from "next/image";
import type { CompanionPreferences, CompanionActivity } from "@/lib/copilot-activity";

export function CompanionPet({ preferences, state = "idle", reaction, resting = false }: { preferences: CompanionPreferences; state?: CompanionActivity["state"]; reaction?: { kind: string; id: number } | null; resting?: boolean }) {
  return <span key={reaction?.id ?? 0} className={`floating-pet-interaction response-${reaction?.kind ?? "none"} ${preferences.motion ? "play-enabled" : ""} ${resting ? "pet-resting" : ""}`} aria-hidden="true"><span className={`floating-pet pet-${state} ${preferences.motion ? "pet-motion" : ""}`}>
    <Image src={`/companions/opendots/${preferences.character}.png`} alt="" width={512} height={512} draggable={false} sizes="180px" className="floating-pet-image" />
  </span>{reaction?.kind === "pet" && <span className="pet-affection">♥</span>}{resting && <span className="pet-snooze">z z z</span>}</span>;
}
