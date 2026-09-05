import { Header } from "@/components/landing/header";
import { Hero } from "@/components/landing/hero";
import { I18nProvider } from "@/core/i18n/context";
import { DEFAULT_LOCALE } from "@/core/i18n/locale";

// The landing stays a synchronous component and pins the default locale:
// the root layout is static by perf boundary, and request-time locale
// detection would turn this page async (breaking the unit render contract).
export default function LandingPage() {
  return (
    <I18nProvider initialLocale={DEFAULT_LOCALE}>
      <div className="min-h-screen w-full bg-[#f8f1e5]">
        <Header />
        <main className="flex w-full flex-col">
          <Hero />
        </main>
      </div>
    </I18nProvider>
  );
}
