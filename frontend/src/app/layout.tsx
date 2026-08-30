import "@/styles/globals.css";
import "katex/dist/katex.min.css";

import { type Metadata } from "next";
import localFont from "next/font/local";

import { ThemeProvider } from "@/components/theme-provider";
import { I18nProvider } from "@/core/i18n/context";
import { detectLocaleServer } from "@/core/i18n/server";

const spaceGrotesk = localFont({
  src: "../assets/fonts/space-grotesk-latin.woff2",
  weight: "500 700",
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: "iDeer",
  description: "A LangChain-based framework for building super agents.",
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const locale = await detectLocaleServer();
  return (
    <html lang={locale} suppressContentEditableWarning suppressHydrationWarning>
      <body className={spaceGrotesk.variable}>
        <ThemeProvider attribute="class" enableSystem disableTransitionOnChange>
          <I18nProvider initialLocale={locale}>{children}</I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
