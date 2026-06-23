import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

const mockScrollPrev = vi.hoisted(() => vi.fn());
const mockScrollNext = vi.hoisted(() => vi.fn());
const mockCanScrollPrev = vi.hoisted(() => vi.fn(() => false));
const mockCanScrollNext = vi.hoisted(() => vi.fn(() => false));
const mockOn = vi.hoisted(() => vi.fn());
const mockOff = vi.hoisted(() => vi.fn());

const defaultMockApi = {
  scrollPrev: mockScrollPrev,
  scrollNext: mockScrollNext,
  canScrollPrev: mockCanScrollPrev,
  canScrollNext: mockCanScrollNext,
  on: mockOn,
  off: mockOff,
};

let _carouselReturnNullApi = false;

vi.mock("embla-carousel-react", () => {
  return {
    __esModule: true,
    default: vi.fn(() => [
      vi.fn(),
      _carouselReturnNullApi ? null : defaultMockApi,
    ]),
  };
});

import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel";

afterEach(() => {
  vi.clearAllMocks();
  _carouselReturnNullApi = false;
  cleanup();
});

describe("Carousel", () => {
  test("renders carousel container", () => {
    render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide 1</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    expect(screen.getByText("Slide 1")).toBeInTheDocument();
  });

  test("renders carousel with role region", () => {
    render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide 1</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    expect(screen.getByRole("region")).toHaveAttribute(
      "aria-roledescription",
      "carousel",
    );
  });

  test("renders multiple carousel items", () => {
    render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide 1</CarouselItem>
          <CarouselItem>Slide 2</CarouselItem>
          <CarouselItem>Slide 3</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    expect(screen.getByText("Slide 1")).toBeInTheDocument();
    expect(screen.getByText("Slide 2")).toBeInTheDocument();
    expect(screen.getByText("Slide 3")).toBeInTheDocument();
  });

  test("renders previous and next buttons", () => {
    render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide 1</CarouselItem>
        </CarouselContent>
        <CarouselPrevious />
        <CarouselNext />
      </Carousel>,
    );
    expect(screen.getByText("Previous slide")).toBeInTheDocument();
    expect(screen.getByText("Next slide")).toBeInTheDocument();
  });

  test("handles ArrowLeft key for previous slide", () => {
    const { container } = render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide 1</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    const region = container.querySelector("[role='region']");
    fireEvent.keyDown(region!, { key: "ArrowLeft" });
    expect(mockScrollPrev).toHaveBeenCalled();
  });

  test("handles ArrowRight key for next slide", () => {
    const { container } = render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide 1</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    const region = container.querySelector("[role='region']");
    fireEvent.keyDown(region!, { key: "ArrowRight" });
    expect(mockScrollNext).toHaveBeenCalled();
  });

  test("handles other keys without scrolling", () => {
    const { container } = render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide 1</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    const region = container.querySelector("[role='region']");
    fireEvent.keyDown(region!, { key: "ArrowUp" });
    expect(mockScrollPrev).not.toHaveBeenCalled();
    expect(mockScrollNext).not.toHaveBeenCalled();
  });

  test("calls setApi callback when api is available", () => {
    const setApi = vi.fn();
    render(
      <Carousel setApi={setApi}>
        <CarouselContent>
          <CarouselItem>Slide 1</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    expect(setApi).toHaveBeenCalled();
  });

  test("registers event listeners on api", () => {
    render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide 1</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    expect(mockOn).toHaveBeenCalledWith("reInit", expect.any(Function));
    expect(mockOn).toHaveBeenCalledWith("select", expect.any(Function));
  });

  test("renders with vertical orientation", () => {
    const { container } = render(
      <Carousel orientation="vertical">
        <CarouselContent>
          <CarouselItem>Slide 1</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    const region = container.querySelector("[role='region']");
    expect(region).toBeInTheDocument();
  });

  test("applies custom className", () => {
    const { container } = render(
      <Carousel className="my-carousel">
        <CarouselContent>
          <CarouselItem>Slide 1</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    const region = container.querySelector("[role='region']");
    expect(region?.getAttribute("class")).toContain("my-carousel");
  });

  test("passes data-slot attribute on carousel", () => {
    const { container } = render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide 1</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    const region = container.querySelector("[role='region']");
    expect(region).toHaveAttribute("data-slot", "carousel");
  });
});

describe("CarouselContent", () => {
  test("renders content wrapper", () => {
    const { container } = render(
      <Carousel>
        <CarouselContent data-testid="content">
          <CarouselItem>Slide</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    const content = container.querySelector("[data-slot='carousel-content']");
    expect(content).toBeInTheDocument();
  });

  test("applies custom className to content", () => {
    const { container } = render(
      <Carousel>
        <CarouselContent className="custom-content">
          <CarouselItem>Slide</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    const inner = container.querySelector("[class*='flex']");
    expect(inner?.getAttribute("class")).toContain("custom-content");
  });
});

describe("CarouselItem", () => {
  test("renders with role group and aria-roledescription", () => {
    render(
      <Carousel>
        <CarouselContent>
          <CarouselItem data-testid="item">Slide 1</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    const item = screen.getByTestId("item");
    expect(item).toHaveAttribute("role", "group");
    expect(item).toHaveAttribute("aria-roledescription", "slide");
  });

  test("applies data-slot attribute", () => {
    render(
      <Carousel>
        <CarouselContent>
          <CarouselItem data-testid="item">Slide</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    expect(screen.getByTestId("item")).toHaveAttribute(
      "data-slot",
      "carousel-item",
    );
  });
});

describe("CarouselPrevious", () => {
  test("is disabled when canScrollPrev is false", () => {
    mockCanScrollPrev.mockReturnValue(false);
    render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide</CarouselItem>
        </CarouselContent>
        <CarouselPrevious />
      </Carousel>,
    );
    expect(screen.getByText("Previous slide").closest("button")).toBeDisabled();
  });

  test("is enabled when canScrollPrev is true", () => {
    mockCanScrollPrev.mockReturnValue(true);
    render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide</CarouselItem>
        </CarouselContent>
        <CarouselPrevious />
      </Carousel>,
    );
    expect(
      screen.getByText("Previous slide").closest("button"),
    ).not.toBeDisabled();
  });

  test("calls scrollPrev when clicked", () => {
    mockCanScrollPrev.mockReturnValue(true);
    render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide</CarouselItem>
        </CarouselContent>
        <CarouselPrevious />
      </Carousel>,
    );
    screen.getByText("Previous slide").closest("button")?.click();
    expect(mockScrollPrev).toHaveBeenCalled();
  });

  test("applies data-slot attribute", () => {
    render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide</CarouselItem>
        </CarouselContent>
        <CarouselPrevious />
      </Carousel>,
    );
    expect(
      screen.getByText("Previous slide").closest("button"),
    ).toHaveAttribute("data-slot", "carousel-previous");
  });
});

describe("CarouselNext", () => {
  test("is disabled when canScrollNext is false", () => {
    mockCanScrollNext.mockReturnValue(false);
    render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide</CarouselItem>
        </CarouselContent>
        <CarouselNext />
      </Carousel>,
    );
    expect(screen.getByText("Next slide").closest("button")).toBeDisabled();
  });

  test("is enabled when canScrollNext is true", () => {
    mockCanScrollNext.mockReturnValue(true);
    render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide</CarouselItem>
        </CarouselContent>
        <CarouselNext />
      </Carousel>,
    );
    expect(screen.getByText("Next slide").closest("button")).not.toBeDisabled();
  });

  test("calls scrollNext when clicked", () => {
    mockCanScrollNext.mockReturnValue(true);
    render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide</CarouselItem>
        </CarouselContent>
        <CarouselNext />
      </Carousel>,
    );
    screen.getByText("Next slide").closest("button")?.click();
    expect(mockScrollNext).toHaveBeenCalled();
  });

  test("applies data-slot attribute", () => {
    render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide</CarouselItem>
        </CarouselContent>
        <CarouselNext />
      </Carousel>,
    );
    expect(screen.getByText("Next slide").closest("button")).toHaveAttribute(
      "data-slot",
      "carousel-next",
    );
  });
});

describe("useCarousel error", () => {
  test("throws when useCarousel is used outside Carousel context", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => {
      render(<CarouselContent data-testid="orphan" />);
    }).toThrow("useCarousel must be used within a <Carousel />");
    spy.mockRestore();
  });
});

describe("Carousel vertical orientation", () => {
  test("renders previous button with vertical positioning class", () => {
    mockCanScrollPrev.mockReturnValue(true);
    const { container } = render(
      <Carousel orientation="vertical">
        <CarouselContent>
          <CarouselItem>Slide</CarouselItem>
        </CarouselContent>
        <CarouselPrevious />
      </Carousel>,
    );
    const prevBtn = screen.getByText("Previous slide").closest("button");
    expect(prevBtn?.className).toContain("-top-12");
    expect(prevBtn?.className).toContain("rotate-90");
  });

  test("renders next button with vertical positioning class", () => {
    mockCanScrollNext.mockReturnValue(true);
    render(
      <Carousel orientation="vertical">
        <CarouselContent>
          <CarouselItem>Slide</CarouselItem>
        </CarouselContent>
        <CarouselNext />
      </Carousel>,
    );
    const nextBtn = screen.getByText("Next slide").closest("button");
    expect(nextBtn?.className).toContain("-bottom-12");
    expect(nextBtn?.className).toContain("rotate-90");
  });

  test("carousel content applies vertical flex class", () => {
    const { container } = render(
      <Carousel orientation="vertical">
        <CarouselContent data-testid="content">
          <CarouselItem>Slide</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    const inner = container.querySelector("[class*='flex']");
    expect(inner?.className).toContain("flex-col");
  });

  test("carousel item applies vertical padding", () => {
    render(
      <Carousel orientation="vertical">
        <CarouselContent>
          <CarouselItem data-testid="item">Slide</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    const item = screen.getByTestId("item");
    expect(item.className).toContain("pt-4");
  });
});

describe("Carousel null api guards", () => {
  test("onSelect early-returns when api is null (line 65)", () => {
    _carouselReturnNullApi = true;
    const setApi = vi.fn();
    render(
      <Carousel setApi={setApi}>
        <CarouselContent>
          <CarouselItem>Slide</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    // setApi should NOT be called because api is null (line 92 guard)
    expect(setApi).not.toHaveBeenCalled();
    // Event listeners should NOT be registered because api is null (line 97 guard)
    expect(mockOn).not.toHaveBeenCalled();
  });

  test("onSelect callback handles null api from event (line 65)", () => {
    render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    // Get the "select" handler registered with api.on
    const selectCall = mockOn.mock.calls.find((c: any) => c[0] === "select");
    expect(selectCall).toBeDefined();
    const selectHandler = selectCall![1];
    // Call the handler with null api - should hit line 65's early return
    selectHandler(null);
    // No crash, no state change
  });

  test("cleans up event listeners on unmount (lines 102-104)", () => {
    const { unmount } = render(
      <Carousel>
        <CarouselContent>
          <CarouselItem>Slide</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    unmount();
    expect(mockOff).toHaveBeenCalledWith("select", expect.any(Function));
  });
});

describe("Carousel orientation fallback", () => {
  test("uses opts.axis y fallback when orientation is falsy", () => {
    // orientation defaults to "horizontal" via default param, so the fallback
    // on line 114 is only reached with an explicitly empty string
    const { container } = render(
      <Carousel orientation={"" as any} opts={{ axis: "y" }}>
        <CarouselContent>
          <CarouselItem data-testid="item">Slide</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    const inner = container.querySelector("[class*='flex']");
    expect(inner?.className).toContain("flex-col");
  });

  test("opts.axis x resolves to horizontal when orientation is falsy", () => {
    const { container } = render(
      <Carousel orientation={"" as any} opts={{ axis: "x" }}>
        <CarouselContent>
          <CarouselItem data-testid="item">Slide</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    const inner = container.querySelector("[class*='flex']");
    expect(inner?.className).toContain("-ml-4");
    expect(inner?.className).not.toContain("flex-col");
  });

  test("defaults to horizontal when neither orientation nor axis provided", () => {
    const { container } = render(
      <Carousel>
        <CarouselContent>
          <CarouselItem data-testid="item">Slide</CarouselItem>
        </CarouselContent>
      </Carousel>,
    );
    const inner = container.querySelector("[class*='flex']");
    expect(inner?.className).toContain("-ml-4");
    expect(inner?.className).not.toContain("flex-col");
  });
});
