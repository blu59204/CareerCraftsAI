import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { ThemeScript } from "@/components/theme/theme-script";
import { AuthGate } from "@/components/auth/AuthGate";
import { OnboardingGuard } from "@/components/auth/OnboardingGuard";
import { AppShell } from "@/components/layout/AppShell";

/**
 * Every signed-in surface lives under this route group, so AuthGate covers the
 * protected set by construction — it cannot drift out of sync the way the
 * hand-maintained path list in the old middleware matcher could.
 */
export default function AppRouteLayout({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider zoneDefault="dark">
      <ThemeScript zoneDefault="dark" />
      <AuthGate>
        <OnboardingGuard>
          <AppShell>{children}</AppShell>
        </OnboardingGuard>
      </AuthGate>
    </ThemeProvider>
  );
}
