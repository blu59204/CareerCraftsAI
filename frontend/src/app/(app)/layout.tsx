import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { ThemeScript } from "@/components/theme/theme-script";
import { OnboardingGuard } from "@/components/auth/OnboardingGuard";
import { AppShell } from "@/components/layout/AppShell";

export default function AppRouteLayout({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider zoneDefault="dark">
      <ThemeScript zoneDefault="dark" />
      <OnboardingGuard>
        <AppShell>{children}</AppShell>
      </OnboardingGuard>
    </ThemeProvider>
  );
}
