"use client";

import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import { motion } from "motion/react";
import { useTheme } from "@/components/theme/ThemeProvider";
import { BlurText } from "@/components/immersive/BlurText";
import { FilmGrain } from "@/components/immersive/FilmGrain";
import { ArrowUpRight, CheckCircle2, Mail, Radar, Sparkles } from "lucide-react";

const PROOF = ["Resume AI", "Real jobs", "Google X-ray", "Gmail", "LinkedIn", "BYOK Models", "Human approval"];
const LIGHT_HERO_VIDEO = "/media/hero/light-bg.mp4";
const DARK_HERO_VIDEO = "/media/hero/dark-bg.mp4";

export function HeroA() {
  const { isLoaded, isSignedIn } = useAuth();
  const { theme } = useTheme();
  const heroVideo = theme === "dark" ? DARK_HERO_VIDEO : LIGHT_HERO_VIDEO;
  const signedIn = isLoaded && isSignedIn;

  return (
    <section className="relative isolate min-h-screen overflow-hidden bg-black pt-16 text-white">
      <video
        key={heroVideo}
        className="absolute inset-0 -z-20 h-full w-full object-cover"
        src={heroVideo}
        autoPlay
        loop
        muted
        playsInline
        preload="auto"
        aria-hidden="true"
      />
      <div className="absolute inset-0 -z-10 bg-gradient-to-b from-white/0 via-white/0 to-black/20 dark:from-black/45 dark:via-black/25 dark:to-black/72" />
      <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_70%_55%_at_50%_12%,transparent_0%,rgba(0,0,0,0.05)_58%,rgba(0,0,0,0.22)_100%)] dark:bg-[radial-gradient(ellipse_70%_55%_at_50%_12%,transparent_0%,rgba(0,0,0,0.18)_58%,rgba(0,0,0,0.72)_100%)]" />
      <FilmGrain />
      <div className="relative z-10 mx-auto flex min-h-[calc(100vh-4rem)] max-w-7xl flex-col justify-center px-6 pb-16 pt-36 text-center md:pt-44">
        <motion.span
          initial={{ opacity: 0, y: 16, filter: "blur(8px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 0.5 }}
          className="font-chrome mx-auto inline-flex w-fit items-center gap-2 rounded-full border border-white/65 bg-white/[0.07] px-4 py-2 text-xs font-semibold text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.62),0_10px_30px_rgba(0,0,0,0.08)] backdrop-blur-[26px] backdrop-saturate-[190%] dark:border-white/20 dark:bg-black/[0.12] dark:text-[#E1E0CC]"
        >
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          6 AI agents working for you 24/7
        </motion.span>

        <motion.h1
          className="mx-auto mt-8 max-w-5xl text-balance font-hero text-5xl font-semibold leading-[0.95] tracking-[-0.04em] text-[#fff9df] drop-shadow-[0_6px_28px_rgba(0,0,0,0.45)] md:text-7xl lg:text-[6.8rem]"
        >
          <BlurText text="Land your next job" />
          <span className="block font-medium italic text-[#f5edcf]">while you sleep</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 18 }}
          animate="show"
          variants={{ show: { opacity: 1, y: 0, transition: { delay: 0.42, duration: 0.55 } } }}
          className="mx-auto mt-7 max-w-2xl text-base leading-8 text-[#DEDBC8]/75 md:text-lg"
        >
          AI agents that find real roles, tailor your resume, draft outreach, and prep you for interviews while you approve every important action.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.62, duration: 0.5 }}
          className="mt-10 flex items-center justify-center gap-3"
        >
          <Link href={signedIn ? "/dashboard" : "/register"}>
            <span className="font-chrome group inline-flex h-12 items-center justify-center gap-2 rounded-full border border-white/65 bg-white/[0.07] px-7 text-sm font-semibold text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.58),0_14px_40px_rgba(0,0,0,0.14)] backdrop-blur-[26px] backdrop-saturate-[190%] transition-all duration-300 hover:gap-3 hover:bg-white/[0.12] dark:border-white/20 dark:bg-black/[0.16] dark:text-[#E1E0CC] dark:hover:bg-black/[0.24] sm:text-base">
              <span className="sm:hidden">{signedIn ? "Open app" : "Start free"}</span>
              <span className="hidden sm:inline">{signedIn ? "Open command center" : "Start free"}</span>
              <ArrowUpRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
            </span>
          </Link>
          <Link href="/#demo">
            <span className="font-chrome inline-flex h-12 items-center justify-center rounded-full border border-white/65 bg-white/[0.08] px-7 text-sm font-semibold text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.58),0_14px_40px_rgba(0,0,0,0.12)] backdrop-blur-[26px] backdrop-saturate-[190%] transition-all duration-300 hover:bg-white/[0.13] dark:border-white/20 dark:bg-white/[0.06] dark:text-[#E1E0CC] dark:hover:bg-white/[0.11] sm:text-base">
              <span className="sm:hidden">How it works</span>
              <span className="hidden sm:inline">See how it works</span>
            </span>
          </Link>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.76, duration: 0.5 }}
          className="mx-auto mt-10 flex max-w-4xl flex-wrap items-center justify-center gap-3"
        >
          {[
            [CheckCircle2, "Approval-safe"],
            [Radar, "Real-time search"],
            [Mail, "Gmail outreach"],
          ].map(([Icon, label]) => {
            const TypedIcon = Icon as typeof CheckCircle2;
            return (
              <span key={label as string} className="font-chrome inline-flex items-center gap-2 rounded-full border border-white/55 bg-white/[0.07] px-3 py-2 text-xs font-semibold text-foreground/75 shadow-[inset_0_1px_0_rgba(255,255,255,0.52),0_8px_24px_rgba(0,0,0,0.10)] backdrop-blur-[24px] backdrop-saturate-[190%] dark:border-white/15 dark:bg-black/[0.12] dark:text-[#DEDBC8]/75">
                <TypedIcon className="h-3.5 w-3.5 text-primary dark:text-[#DEDBC8]" />
                {label as string}
              </span>
            );
          })}
        </motion.div>

      </div>
      <div className="relative z-10 border-y border-white/10 bg-black/45 py-5 backdrop-blur-xl">
        <div className="flex overflow-hidden">
          <div className="animate-marquee-left flex min-w-full items-center gap-10 whitespace-nowrap pr-10">
            {[...PROOF, ...PROOF].map((item, index) => (
              <span key={`${item}-${index}`} className="text-sm uppercase tracking-[0.28em] text-muted-foreground">
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
