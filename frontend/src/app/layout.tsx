import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { Providers } from "@/components/layout/Providers";
import { Sidebar } from "@/components/layout/Sidebar";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "JobAgent AI",
  description: "Automate your job search with AI agents",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body className={inter.className}>
          <Providers>
            <div className="flex min-h-screen">
              <Sidebar />
              <div className="flex-1">{children}</div>
            </div>
          </Providers>
        </body>
      </html>
    </ClerkProvider>
  );
}
