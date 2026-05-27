"use client";

import { useState } from "react";
import { toast } from "sonner";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";

export default function ContactPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !message.trim()) {
      toast.error("Fill in all fields");
      return;
    }
    setSending(true);
    await new Promise((r) => setTimeout(r, 800));
    setSending(false);
    toast.success("Message sent — we'll reply within 24 hours");
    setName("");
    setEmail("");
    setMessage("");
  };

  return (
    <div className="mx-auto max-w-xl px-6 py-24">
      <div className="mb-3 text-sm font-medium text-primary">Contact</div>
      <h1 className="text-4xl font-medium">Get in touch.</h1>
      <p className="mt-4 text-muted-foreground">
        Questions, feedback, or partnership inquiries — we read everything.
      </p>

      <form onSubmit={handleSubmit} className="mt-10 space-y-4">
        <div>
          <label className="mb-1.5 block text-sm font-medium">Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Your name"
            className="h-11 w-full rounded-2xl border border-border bg-card/40 px-4 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="h-11 w-full rounded-2xl border border-border bg-card/40 px-4 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium">Message</label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="What can we help you with?"
            rows={5}
            className="w-full resize-none rounded-2xl border border-border bg-card/40 px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <LiquidGlassButton tone="primary" disabled={sending} className="w-full">
          {sending ? "Sending…" : "Send message"}
        </LiquidGlassButton>
      </form>

      <p className="mt-8 text-sm text-muted-foreground">
        Or email us directly at{" "}
        <a href="mailto:hello@careercraft.ai" className="text-primary hover:underline">
          hello@careercraft.ai
        </a>
      </p>
    </div>
  );
}
