import "@/styles/globals.css";

import { type Metadata } from "next";

import { ThemeProvider } from "@/components/theme-provider";
import { DEFAULT_LOCALE } from "@/core/i18n/locale";

export const metadata: Metadata = {
  title: "iDeer",
  description: "A LangChain-based framework for building super agents.",
};

// Perf boundary (see tests/unit/app/layout-boundaries.test.ts): the root
// layout stays static — no request-time locale detection, no client i18n
// provider and no rich-content stylesheets. Routes that need them own them
// (workspace, docs, blog, artifacts layouts, and the landing page below).
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang={DEFAULT_LOCALE} suppressContentEditableWarning suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" enableSystem disableTransitionOnChange>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
