import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { ThemeScript } from "@/components/theme/theme-script";
import { MarketingNavbar } from "@/components/marketing/Navbar";
import { MarketingFooter } from "@/components/marketing/Footer";

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider zoneDefault="light">
      <ThemeScript zoneDefault="light" />
      <div className="min-h-screen bg-background text-foreground">
        <MarketingNavbar />
        <main>{children}</main>
        <MarketingFooter />
      </div>
    </ThemeProvider>
  );
}
