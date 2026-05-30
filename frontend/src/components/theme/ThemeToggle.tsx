import ThemeSwitch from "@/components/ui/theme-switch";

export function ThemeToggle({ className = "" }: { className?: string }) {
  return <ThemeSwitch className={className} />;
}
