import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/lib/theme-provider";

export const metadata: Metadata = {
  title: "SEC-OPS V8 Control Center",
  description: "Enterprise Retail Loss Prevention & Surveillance CV System",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning className="dark" data-theme="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                const saved = localStorage.getItem("secops_theme") || "system";
                let active = "dark";
                if (saved === "system") {
                  active = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
                } else {
                  active = saved;
                }
                document.documentElement.classList.remove("dark", "light");
                document.documentElement.classList.add(active);
                document.documentElement.setAttribute("data-theme", active);
              } catch (_) {}
            `,
          }}
        />
      </head>
      <body className="bg-[var(--bg-canvas)] text-[var(--text-primary)] min-h-screen antialiased selection:bg-[#4FD1B3]/20 selection:text-[#4FD1B3] transition-colors duration-200">
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
