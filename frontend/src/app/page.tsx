import { Header } from "@/components/landing/header";
import { Hero } from "@/components/landing/hero";

export default function LandingPage() {
  return (
    // The landing page keeps its own dark marketing look by scoping the
    // `dark` class locally, instead of forcing the global theme (P0-2A).
    <div className="dark min-h-screen w-full bg-[#0a0a0a]">
      <Header />
      <main className="flex w-full flex-col">
        <Hero />
      </main>
    </div>
  );
}
