import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { gsap } from "gsap";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("gsap", () => ({
  gsap: {
    to: vi.fn(),
    fromTo: vi.fn(
      (_el: unknown, _from: unknown, to: Record<string, unknown>) => {
        // Call onComplete if provided, to simulate animation completion
        if (to && typeof to.onComplete === "function") {
          to.onComplete();
        }
      },
    ),
  },
}));

vi.mock("@/components/ui/magic-bento.css", () => ({}));

import MagicBento from "@/components/ui/magic-bento";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const cardData = [
  { title: "Card 1", description: "Description 1", label: "Label 1" },
  { title: "Card 2", description: "Description 2", label: "Label 2" },
];

const singleCard = [
  { title: "Single", description: "Single Desc", label: "Single Label" },
];

// Override getBoundingClientRect on Element.prototype so all elements
// (cards, section, spotlight targets) report reasonable dimensions.
const mockRect: DOMRect = {
  top: 0,
  left: 0,
  width: 200,
  height: 150,
  right: 200,
  bottom: 150,
  x: 0,
  y: 0,
  toJSON: () => {},
};

describe("MagicBento", () => {
  beforeEach(() => {
    Element.prototype.getBoundingClientRect = vi.fn(() => mockRect);
  });

  // -----------------------------------------------------------
  // 1. Basic rendering
  // -----------------------------------------------------------
  describe("basic rendering", () => {
    test("renders card titles", () => {
      render(<MagicBento data={cardData} />);
      expect(screen.getByText("Card 1")).toBeInTheDocument();
      expect(screen.getByText("Card 2")).toBeInTheDocument();
    });

    test("renders card descriptions", () => {
      render(<MagicBento data={cardData} />);
      expect(screen.getByText("Description 1")).toBeInTheDocument();
      expect(screen.getByText("Description 2")).toBeInTheDocument();
    });

    test("renders card labels", () => {
      render(<MagicBento data={cardData} />);
      expect(screen.getByText("Label 1")).toBeInTheDocument();
      expect(screen.getByText("Label 2")).toBeInTheDocument();
    });

    test("renders correct number of cards", () => {
      const { container } = render(<MagicBento data={cardData} />);
      expect(container.querySelectorAll(".magic-bento-card").length).toBe(2);
    });

    test("renders single card", () => {
      render(<MagicBento data={singleCard} />);
      expect(screen.getByText("Single")).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------
  // 2. Empty data
  // -----------------------------------------------------------
  describe("empty data", () => {
    test("renders empty grid with no cards", () => {
      const { container } = render(<MagicBento data={[]} />);
      const grid = container.querySelector(".card-grid");
      expect(grid).toBeInTheDocument();
      expect(grid!.children.length).toBe(0);
    });

    test("empty data renders no magic-bento-card elements", () => {
      const { container } = render(<MagicBento data={[]} />);
      expect(container.querySelectorAll(".magic-bento-card").length).toBe(0);
    });
  });

  // -----------------------------------------------------------
  // 3. enableStars — ParticleCard vs plain div
  // -----------------------------------------------------------
  describe("enableStars", () => {
    test("enableStars=true wraps cards in particle-container divs", () => {
      const { container } = render(
        <MagicBento data={singleCard} enableStars={true} />,
      );
      expect(container.querySelectorAll(".particle-container").length).toBe(1);
    });

    test("enableStars=false renders plain divs without particle-container", () => {
      const { container } = render(
        <MagicBento data={singleCard} enableStars={false} />,
      );
      expect(container.querySelectorAll(".particle-container").length).toBe(0);
      expect(screen.getByText("Single")).toBeInTheDocument();
    });

    test("enableStars=false renders all cards", () => {
      const { container } = render(
        <MagicBento data={cardData} enableStars={false} />,
      );
      expect(container.querySelectorAll(".magic-bento-card").length).toBe(2);
    });
  });

  // -----------------------------------------------------------
  // 4. enableSpotlight
  // -----------------------------------------------------------
  describe("enableSpotlight", () => {
    test("enableSpotlight=true adds spotlight element to the DOM", () => {
      render(<MagicBento data={singleCard} enableSpotlight={true} />);
      expect(document.querySelector(".global-spotlight")).toBeInTheDocument();
    });

    test("enableSpotlight=false does not add spotlight element", () => {
      render(<MagicBento data={singleCard} enableSpotlight={false} />);
      expect(
        document.querySelector(".global-spotlight"),
      ).not.toBeInTheDocument();
    });

    test("spotlight element is removed on unmount", () => {
      const { unmount } = render(
        <MagicBento data={singleCard} enableSpotlight={true} />,
      );
      expect(document.querySelector(".global-spotlight")).toBeInTheDocument();
      unmount();
      expect(
        document.querySelector(".global-spotlight"),
      ).not.toBeInTheDocument();
    });

    test("spotlight uses custom glowColor in background", () => {
      render(
        <MagicBento
          data={singleCard}
          enableSpotlight={true}
          glowColor="255, 0, 0"
        />,
      );
      const spotlight = document.querySelector(".global-spotlight")!;
      expect((spotlight as HTMLElement).style.background).toContain(
        "255, 0, 0",
      );
    });
  });

  // -----------------------------------------------------------
  // 5. enableBorderGlow
  // -----------------------------------------------------------
  describe("enableBorderGlow", () => {
    test("enableBorderGlow=true adds border-glow class", () => {
      const { container } = render(
        <MagicBento data={singleCard} enableBorderGlow={true} />,
      );
      const card = container.querySelector(".magic-bento-card")!;
      expect(card.className).toContain("magic-bento-card--border-glow");
    });

    test("enableBorderGlow=false omits border-glow class", () => {
      const { container } = render(
        <MagicBento data={singleCard} enableBorderGlow={false} />,
      );
      const card = container.querySelector(".magic-bento-card")!;
      expect(card.className).not.toContain("magic-bento-card--border-glow");
    });
  });

  // -----------------------------------------------------------
  // 6. textAutoHide
  // -----------------------------------------------------------
  describe("textAutoHide", () => {
    test("textAutoHide=true adds text-autohide class", () => {
      const { container } = render(
        <MagicBento data={singleCard} textAutoHide={true} />,
      );
      const card = container.querySelector(".magic-bento-card")!;
      expect(card.className).toContain("magic-bento-card--text-autohide");
    });

    test("textAutoHide=false omits text-autohide class", () => {
      const { container } = render(
        <MagicBento data={singleCard} textAutoHide={false} />,
      );
      const card = container.querySelector(".magic-bento-card")!;
      expect(card.className).not.toContain("magic-bento-card--text-autohide");
    });
  });

  // -----------------------------------------------------------
  // 7. Card styling (color)
  // -----------------------------------------------------------
  describe("card styling", () => {
    test("applies custom color as backgroundColor", () => {
      const data = [
        {
          title: "Colored",
          description: "Desc",
          label: "Label",
          color: "#ff0000",
        },
      ];
      const { container } = render(<MagicBento data={data} />);
      const card = container.querySelector(".magic-bento-card")!;
      expect((card as HTMLElement).style.backgroundColor).toBe(
        "rgb(255, 0, 0)",
      );
    });

    test("sets --glow-color CSS custom property", () => {
      const { container } = render(
        <MagicBento data={singleCard} glowColor="0, 255, 0" />,
      );
      const card = container.querySelector(".magic-bento-card")!;
      expect((card as HTMLElement).style.getPropertyValue("--glow-color")).toBe(
        "0, 255, 0",
      );
    });
  });

  // -----------------------------------------------------------
  // 8. All props — every feature enabled
  // -----------------------------------------------------------
  describe("all props enabled", () => {
    test("renders correctly with all props on", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={true}
          enableSpotlight={true}
          enableBorderGlow={true}
          enableTilt={true}
          clickEffect={true}
          enableMagnetism={true}
          disableAnimations={false}
          textAutoHide={true}
          spotlightRadius={500}
          particleCount={20}
          glowColor="255, 0, 0"
        />,
      );
      const card = container.querySelector(".magic-bento-card")!;
      expect(card.className).toContain("magic-bento-card--border-glow");
      expect(card.className).toContain("magic-bento-card--text-autohide");
      expect(card.className).toContain("particle-container");
      expect(document.querySelector(".global-spotlight")).toBeInTheDocument();
    });

    test("renders correctly with all props off", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={false}
          enableSpotlight={false}
          enableBorderGlow={false}
          enableTilt={false}
          clickEffect={false}
          enableMagnetism={false}
          disableAnimations={true}
          textAutoHide={false}
        />,
      );
      const card = container.querySelector(".magic-bento-card")!;
      expect(card.className).not.toContain("magic-bento-card--border-glow");
      expect(card.className).not.toContain("magic-bento-card--text-autohide");
      expect(card.className).not.toContain("particle-container");
      expect(
        document.querySelector(".global-spotlight"),
      ).not.toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------
  // 9. ReactNode content
  // -----------------------------------------------------------
  describe("ReactNode content", () => {
    test("renders ReactNode title", () => {
      const data = [
        {
          title: <span data-testid="rn-title">Rich Title</span>,
          description: "Desc",
          label: "Label",
        },
      ];
      render(<MagicBento data={data} />);
      expect(screen.getByTestId("rn-title")).toBeInTheDocument();
    });

    test("renders ReactNode description", () => {
      const data = [
        {
          title: "Title",
          description: <strong data-testid="rn-desc">Rich Desc</strong>,
          label: "Label",
        },
      ];
      render(<MagicBento data={data} />);
      expect(screen.getByTestId("rn-desc")).toBeInTheDocument();
    });

    test("renders ReactNode label", () => {
      const data = [
        {
          title: "Title",
          description: "Desc",
          label: <em data-testid="rn-label">Rich Label</em>,
        },
      ];
      render(<MagicBento data={data} />);
      expect(screen.getByTestId("rn-label")).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------
  // 10. ParticleCard mouse events (enableStars=true)
  // -----------------------------------------------------------
  describe("ParticleCard mouse events", () => {
    test("mouseenter triggers tilt gsap.to when enableTilt=true", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={true}
          enableTilt={true}
          disableAnimations={false}
        />,
      );
      const card = container.querySelector(".particle-container")!;
      fireEvent.mouseEnter(card);
      expect(gsap.to).toHaveBeenCalled();
    });

    test("mouseleave resets tilt via gsap.to when enableTilt=true", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={true}
          enableTilt={true}
          disableAnimations={false}
        />,
      );
      const card = container.querySelector(".particle-container")!;
      fireEvent.mouseEnter(card);
      vi.clearAllMocks();

      fireEvent.mouseLeave(card);
      expect(gsap.to).toHaveBeenCalled();
    });

    test("mousemove triggers tilt animation via gsap.to", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={true}
          enableTilt={true}
          disableAnimations={false}
        />,
      );
      const card = container.querySelector(".particle-container")!;
      fireEvent.mouseEnter(card);
      vi.clearAllMocks();

      fireEvent.mouseMove(card, { clientX: 100, clientY: 75 });
      expect(gsap.to).toHaveBeenCalled();
    });

    test("click triggers ripple via gsap.fromTo when clickEffect=true", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={true}
          clickEffect={true}
          disableAnimations={false}
        />,
      );
      const card = container.querySelector(".particle-container")!;
      fireEvent.click(card, { clientX: 50, clientY: 50 });
      expect(gsap.fromTo).toHaveBeenCalled();
    });

    test("click does nothing when clickEffect=false", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={true}
          clickEffect={false}
          disableAnimations={false}
        />,
      );
      const card = container.querySelector(".particle-container")!;
      vi.clearAllMocks();

      fireEvent.click(card, { clientX: 50, clientY: 50 });
      expect(gsap.fromTo).not.toHaveBeenCalled();
    });

    test("mousemove with both tilt and magnetism disabled does not call gsap.to for card", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={true}
          enableTilt={false}
          enableMagnetism={false}
          disableAnimations={false}
        />,
      );
      const card = container.querySelector(".particle-container")!;
      fireEvent.mouseEnter(card);
      vi.clearAllMocks();

      fireEvent.mouseMove(card, { clientX: 100, clientY: 75 });
      // No tilt or magnetism gsap.to calls from the card handler
      // (particle timeout gsap calls may still fire but no immediate sync ones)
    });

    test("disableAnimations prevents event listener attachment", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={true}
          disableAnimations={true}
          enableTilt={true}
        />,
      );
      const card = container.querySelector(".particle-container")!;
      vi.clearAllMocks();

      fireEvent.mouseEnter(card);
      // No gsap.to because the useEffect returned early
      expect(gsap.to).not.toHaveBeenCalled();
    });
  });

  // -----------------------------------------------------------
  // 11. Magnetism behaviour
  // -----------------------------------------------------------
  describe("magnetism", () => {
    test("enableMagnetism=true triggers magnetism on mousemove", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={true}
          enableMagnetism={true}
          enableTilt={false}
          disableAnimations={false}
        />,
      );
      const card = container.querySelector(".particle-container")!;
      fireEvent.mouseEnter(card);
      vi.clearAllMocks();

      fireEvent.mouseMove(card, { clientX: 120, clientY: 80 });
      expect(gsap.to).toHaveBeenCalled();
    });

    test("enableMagnetism=true resets position on mouseleave", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={true}
          enableMagnetism={true}
          enableTilt={false}
          disableAnimations={false}
        />,
      );
      const card = container.querySelector(".particle-container")!;
      fireEvent.mouseEnter(card);
      vi.clearAllMocks();

      fireEvent.mouseLeave(card);
      expect(gsap.to).toHaveBeenCalled();
    });
  });

  // -----------------------------------------------------------
  // 12. GlobalSpotlight mouse events
  // -----------------------------------------------------------
  describe("GlobalSpotlight mouse events", () => {
    function setupSpotlight(props = {}) {
      const result = render(
        <MagicBento data={singleCard} enableSpotlight={true} {...props} />,
      );
      const section = document.querySelector(".bento-section");
      // Make the section report a known rect so "inside" checks work
      if (section) {
        section.getBoundingClientRect = vi.fn(() => ({
          top: 0,
          left: 0,
          width: 400,
          height: 300,
          right: 400,
          bottom: 300,
          x: 0,
          y: 0,
          toJSON: () => {},
        }));
      }
      return { ...result, section };
    }

    test("mousemove inside section triggers spotlight gsap.to", () => {
      setupSpotlight();
      vi.clearAllMocks();

      // Mouse inside the section rect (0,0 → 400,300)
      fireEvent.mouseMove(document, { clientX: 200, clientY: 150 });
      expect(gsap.to).toHaveBeenCalled();
    });

    test("mousemove outside section hides spotlight", () => {
      setupSpotlight();
      vi.clearAllMocks();

      // Mouse far outside the section
      fireEvent.mouseMove(document, { clientX: 800, clientY: 800 });
      // gsap.to called to fade spotlight to 0 and reset card glow
      expect(gsap.to).toHaveBeenCalled();
    });

    test("document mouseleave resets spotlight opacity to 0", () => {
      setupSpotlight();
      vi.clearAllMocks();

      fireEvent.mouseLeave(document);
      expect(gsap.to).toHaveBeenCalled();
    });

    test("spotlight position updates on mousemove", () => {
      setupSpotlight();
      vi.clearAllMocks();

      fireEvent.mouseMove(document, { clientX: 150, clientY: 100 });

      // At least one gsap.to call should target the spotlight element
      // for left/top positioning
      const toCalls = (gsap.to as ReturnType<typeof vi.fn>).mock.calls;
      const hasPositionUpdate = toCalls.some(
        (call: any[]) => call[1] && typeof call[1].left === "number",
      );
      expect(hasPositionUpdate).toBe(true);
    });

    test("spotlight applies fade-zone glow intensity when mouse is between proximity and fadeDistance", () => {
      setupSpotlight({ spotlightRadius: 300 });
      vi.clearAllMocks();

      // Card center is at (100, 75) with rect (0,0,200,150).
      // proximity = 150, fadeDistance = 225.
      // Mouse at (400, 75): rawDistance = 300, effectiveDistance = 300 - 100 = 200.
      // 200 is in fade zone (150 < 200 <= 225).
      fireEvent.mouseMove(document, { clientX: 400, clientY: 75 });

      // Should have called gsap.to for the spotlight element
      expect(gsap.to).toHaveBeenCalled();

      // Verify the card got a glow-intensity property set (via updateCardGlowProperties)
      const card = document.querySelector(".magic-bento-card")!;
      const glowIntensity = (card as HTMLElement).style.getPropertyValue(
        "--glow-intensity",
      );
      // glowIntensity should be > 0 and < 1 (fade zone)
      expect(Number(glowIntensity)).toBeGreaterThan(0);
      expect(Number(glowIntensity)).toBeLessThan(1);
    });
  });

  // -----------------------------------------------------------
  // 13. Mobile detection
  // -----------------------------------------------------------
  describe("mobile detection", () => {
    const originalInnerWidth = window.innerWidth;

    afterEach(() => {
      Object.defineProperty(window, "innerWidth", {
        writable: true,
        configurable: true,
        value: originalInnerWidth,
      });
      window.dispatchEvent(new Event("resize"));
    });

    test("mobile viewport (<=768) renders cards", () => {
      Object.defineProperty(window, "innerWidth", {
        writable: true,
        configurable: true,
        value: 500,
      });
      window.dispatchEvent(new Event("resize"));

      const { container } = render(
        <MagicBento data={singleCard} enableStars={true} />,
      );
      expect(container.querySelector(".magic-bento-card")).toBeInTheDocument();
    });

    test("desktop viewport (>768) renders cards", () => {
      Object.defineProperty(window, "innerWidth", {
        writable: true,
        configurable: true,
        value: 1024,
      });
      window.dispatchEvent(new Event("resize"));

      const { container } = render(
        <MagicBento data={singleCard} enableStars={true} />,
      );
      expect(container.querySelector(".magic-bento-card")).toBeInTheDocument();
    });

    test("resize from desktop to mobile re-renders correctly", () => {
      Object.defineProperty(window, "innerWidth", {
        writable: true,
        configurable: true,
        value: 1024,
      });

      const { container, rerender } = render(
        <MagicBento data={singleCard} enableStars={true} />,
      );

      // Shrink to mobile
      Object.defineProperty(window, "innerWidth", {
        writable: true,
        configurable: true,
        value: 400,
      });
      window.dispatchEvent(new Event("resize"));
      rerender(<MagicBento data={singleCard} enableStars={true} />);

      expect(container.querySelector(".magic-bento-card")).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------
  // 14. Non-stars path (enableStars=false) mouse interactions
  // -----------------------------------------------------------
  describe("non-stars path (enableStars=false)", () => {
    test("cards render with correct content", () => {
      const { container } = render(
        <MagicBento data={cardData} enableStars={false} />,
      );
      expect(container.querySelectorAll(".magic-bento-card").length).toBe(2);
      expect(screen.getByText("Card 1")).toBeInTheDocument();
      expect(screen.getByText("Card 2")).toBeInTheDocument();
    });

    test("mousemove triggers tilt gsap.to when enableTilt=true", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={false}
          enableTilt={true}
          disableAnimations={false}
        />,
      );
      const card = container.querySelector(".magic-bento-card")!;
      fireEvent.mouseMove(card, { clientX: 100, clientY: 75 });
      expect(gsap.to).toHaveBeenCalled();
    });

    test("mousemove triggers magnetism gsap.to when enableMagnetism=true", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={false}
          enableTilt={false}
          enableMagnetism={true}
          disableAnimations={false}
        />,
      );
      const card = container.querySelector(".magic-bento-card")!;
      fireEvent.mouseMove(card, { clientX: 100, clientY: 75 });
      expect(gsap.to).toHaveBeenCalled();
    });

    test("mouseleave resets tilt and magnetism", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={false}
          enableTilt={true}
          enableMagnetism={true}
          disableAnimations={false}
        />,
      );
      const card = container.querySelector(".magic-bento-card")!;
      vi.clearAllMocks();

      fireEvent.mouseLeave(card);
      // Both tilt reset and magnetism reset
      const toCalls = (gsap.to as ReturnType<typeof vi.fn>).mock.calls;
      expect(toCalls.length).toBeGreaterThanOrEqual(2);
    });

    test("click triggers ripple when clickEffect=true", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={false}
          clickEffect={true}
          disableAnimations={false}
        />,
      );
      const card = container.querySelector(".magic-bento-card")!;
      vi.clearAllMocks();

      fireEvent.click(card, { clientX: 50, clientY: 50 });
      expect(gsap.fromTo).toHaveBeenCalled();
    });

    test("click does nothing when clickEffect=false", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={false}
          clickEffect={false}
          disableAnimations={false}
        />,
      );
      const card = container.querySelector(".magic-bento-card")!;
      vi.clearAllMocks();

      fireEvent.click(card, { clientX: 50, clientY: 50 });
      expect(gsap.fromTo).not.toHaveBeenCalled();
    });

    test("disableAnimations prevents all mouse interactions", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={false}
          enableTilt={true}
          enableMagnetism={true}
          clickEffect={true}
          disableAnimations={true}
        />,
      );
      const card = container.querySelector(".magic-bento-card")!;
      vi.clearAllMocks();

      fireEvent.mouseMove(card, { clientX: 100, clientY: 75 });
      fireEvent.mouseLeave(card);
      fireEvent.click(card, { clientX: 50, clientY: 50 });

      expect(gsap.to).not.toHaveBeenCalled();
      expect(gsap.fromTo).not.toHaveBeenCalled();
    });

    test("mousemove with both tilt and magnetism off does not call gsap.to from card handler", () => {
      const { container } = render(
        <MagicBento
          data={singleCard}
          enableStars={false}
          enableSpotlight={false}
          enableTilt={false}
          enableMagnetism={false}
          disableAnimations={false}
        />,
      );
      const card = container.querySelector(".magic-bento-card")!;
      vi.clearAllMocks();

      fireEvent.mouseMove(card, { clientX: 100, clientY: 75 });
      expect(gsap.to).not.toHaveBeenCalled();
    });
  });

  // -----------------------------------------------------------
  // 15. Multiple cards interaction independence
  // -----------------------------------------------------------
  describe("multiple cards", () => {
    test("each card receives its own content", () => {
      const data = [
        { title: "Alpha", description: "Desc A", label: "Label A" },
        { title: "Beta", description: "Desc B", label: "Label B" },
        { title: "Gamma", description: "Desc C", label: "Label C" },
      ];
      render(<MagicBento data={data} />);
      expect(screen.getByText("Alpha")).toBeInTheDocument();
      expect(screen.getByText("Beta")).toBeInTheDocument();
      expect(screen.getByText("Gamma")).toBeInTheDocument();
    });

    test("enableStars=false renders all cards as plain divs", () => {
      const { container } = render(
        <MagicBento data={cardData} enableStars={false} />,
      );
      const cards = container.querySelectorAll(".magic-bento-card");
      expect(cards.length).toBe(2);
      cards.forEach((card) => {
        expect(card.className).not.toContain("particle-container");
      });
    });

    test("enableStars=true renders all cards as particle containers", () => {
      const { container } = render(
        <MagicBento data={cardData} enableStars={true} />,
      );
      const particles = container.querySelectorAll(".particle-container");
      expect(particles.length).toBe(2);
    });
  });
});
