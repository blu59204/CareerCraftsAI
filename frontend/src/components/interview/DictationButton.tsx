"use client";

import { useEffect, useRef, useState } from "react";
import { Microphone, MicrophoneSlash, Stop } from "@phosphor-icons/react";
import { toast } from "sonner";
import { IslandButton } from "@/components/vanguard";
import { appendTranscript, dictationErrorMessage } from "@/lib/dictation";

// The Web Speech API is not in TypeScript's DOM types.
interface SpeechResult {
  isFinal: boolean;
  0: { transcript: string };
}
interface SpeechEvent {
  resultIndex: number;
  results: ArrayLike<SpeechResult>;
}
interface Recognition {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}
type RecognitionConstructor = new () => Recognition;

function recognitionConstructor(): RecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: RecognitionConstructor;
    webkitSpeechRecognition?: RecognitionConstructor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

interface DictationButtonProps {
  /** Receives the updated text; pass the current text through `current`. */
  current: string;
  onText: (next: string) => void;
}

/** Push-to-dictate for an answer box. Falls back to a disabled, explained state. */
export function DictationButton({ current, onText }: DictationButtonProps) {
  const [supported, setSupported] = useState(true);
  const [listening, setListening] = useState(false);
  const recognition = useRef<Recognition | null>(null);
  // Final phrases are appended to whatever was in the box when they arrive,
  // so typing during dictation is kept.
  const latest = useRef(current);
  latest.current = current;

  useEffect(() => {
    setSupported(recognitionConstructor() !== null);
    return () => recognition.current?.stop();
  }, []);

  const toggle = () => {
    if (listening) {
      recognition.current?.stop();
      return;
    }
    const Ctor = recognitionConstructor();
    if (!Ctor) return;
    const next = new Ctor();
    next.continuous = true;
    next.interimResults = false;
    next.lang = typeof navigator !== "undefined" && navigator.language ? navigator.language : "en-US";
    next.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        if (event.results[i].isFinal) {
          latest.current = appendTranscript(latest.current, event.results[i][0].transcript);
          onText(latest.current);
        }
      }
    };
    next.onerror = (event) => {
      const message = dictationErrorMessage(event.error);
      if (message) toast.error(message);
    };
    next.onend = () => setListening(false);
    recognition.current = next;
    next.start();
    setListening(true);
  };

  if (!supported) {
    return (
      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        <MicrophoneSlash size={14} weight="light" aria-hidden />
        Dictation isn&rsquo;t available in this browser. Type your answer instead.
      </p>
    );
  }

  return (
    <IslandButton
      tone="ghost"
      size="sm"
      onClick={toggle}
      aria-pressed={listening}
      icon={
        listening ? <Stop size={14} weight="fill" aria-hidden /> : <Microphone size={14} weight="light" aria-hidden />
      }
    >
      {listening ? "Stop dictating" : "Dictate answer"}
    </IslandButton>
  );
}
