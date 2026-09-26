import type { Metadata } from "next";
import { ContactForm } from "@/components/marketing/ContactForm";
import { Breadcrumbs } from "@/components/seo/Breadcrumbs";

export const metadata: Metadata = {
  title: "Contact",
  description: "Questions, feedback, or partnership inquiries for CareerCraft AI — we read everything.",
  alternates: { canonical: "/contact" },
};

export default function ContactPage() {
  return (
    <div className="mx-auto max-w-xl px-6 py-24">
      <Breadcrumbs trail={[{ name: "Contact", href: "/contact" }]} />
      <div className="mb-3 text-sm font-medium text-primary">Contact</div>
      <h1 className="text-4xl font-medium">Get in touch.</h1>
      <p className="mt-4 text-muted-foreground">
        Questions, feedback, or partnership inquiries — we read everything.
      </p>

      <ContactForm />

      <p className="mt-8 text-sm text-muted-foreground">
        Or email us directly at{" "}
        <a href="mailto:hello@careercraftsai.me" className="text-primary hover:underline">
          hello@careercraftsai.me
        </a>
      </p>
    </div>
  );
}
