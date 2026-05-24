import { AppSidebar } from "./AppSidebar";
import { AppTopbar } from "./AppTopbar";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <AppSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppTopbar />
        <main className="flex-1 px-6 py-8 md:px-8">{children}</main>
      </div>
    </div>
  );
}
