import type { Metadata } from "next";
import { DM_Sans, Instrument_Serif, Playfair_Display } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { Providers } from "@/components/layout/Providers";
import "./globals.css";

// Inter was downloaded on every page load but never used: it sat only as a
// fallback behind DM Sans in the sans stack, so it rendered only if DM Sans
// failed. It is also the single most over-used typeface in generated UI.
// Dropped — the stack falls through to ui-sans-serif/system-ui instead.
const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
  variable: "--font-dm-sans",
  display: "swap",
});
const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: "italic",
  variable: "--font-instrument-serif",
  display: "swap",
});
const playfair = Playfair_Display({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  style: ["normal", "italic"],
  variable: "--font-playfair",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CareerCraft AI — Apply smarter. Tailor faster.",
  description: "AI job-search copilot for students and freshers.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // No Clerk prebuilt UI is rendered anywhere in this app (no <SignIn/>,
    // <SignUp/> or <UserButton/>), so no "Secured by Clerk" badge appears.
    // ClerkProvider only supplies session context to the headless hooks.
    <ClerkProvider signInUrl="/login" signUpUrl="/login">
      <html lang="en" className={`${dmSans.variable} ${instrumentSerif.variable} ${playfair.variable}`} suppressHydrationWarning>
        <body className="font-sans antialiased">
          <Providers>{children}</Providers>
        </body>
      </html>
    </ClerkProvider>
  );
}
