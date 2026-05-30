"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

interface VideoBackdropProps {
  src?: string;
  poster?: string;
  className?: string;
  opacity?: number;
}

export function VideoBackdrop({ src, poster, className, opacity = 0.3 }: VideoBackdropProps) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <div
        aria-hidden
        className={cn("absolute inset-0 bg-[radial-gradient(circle_at_70%_30%,hsl(var(--primary)/0.22),transparent_36%),radial-gradient(circle_at_20%_80%,hsl(var(--accent)/0.18),transparent_42%)]", className)}
      />
    );
  }

  return (
    <video
      aria-hidden
      autoPlay
      muted
      loop
      playsInline
      poster={poster}
      onError={() => setFailed(true)}
      className={cn("absolute inset-0 h-full w-full object-cover", className)}
      style={{ opacity }}
      src={src}
    />
  );
}
