import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { ErrorBoundary } from "@/components/ui/error-boundary";

function BuggyComponent({ message = "Test error" }: { message?: string }) {
  throw new Error(message);
}

function MaybeBuggy({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error("Conditional error");
  }
  return <div data-testid="safe-child">Recovered</div>;
}

function SafeComponent() {
  return <div data-testid="safe-child">Safe content</div>;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ErrorBoundary", () => {
  test("renders children normally when no error occurs", () => {
    render(
      <ErrorBoundary>
        <SafeComponent />
      </ErrorBoundary>,
    );
    expect(screen.getByTestId("safe-child")).toHaveTextContent("Safe content");
  });

  test("catches rendering error and displays fallback UI", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <BuggyComponent />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("error-boundary-fallback")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  test("shows default fallback UI with title and retry button", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <BuggyComponent message="Custom error message" />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("error-boundary-fallback")).toBeInTheDocument();
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("Try Again")).toBeInTheDocument();
  });

  test("renders custom fallback ReactNode when fallback prop is provided", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary
        fallback={<div data-testid="custom-fallback">Custom Error UI</div>}
      >
        <BuggyComponent />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("custom-fallback")).toBeInTheDocument();
    expect(screen.getByText("Custom Error UI")).toBeInTheDocument();
    expect(
      screen.queryByTestId("error-boundary-fallback"),
    ).not.toBeInTheDocument();
  });

  test("calls fallback render function with error and reset function", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    const customFallback = vi.fn((error: Error, reset: () => void) => (
      <div data-testid="render-fallback">
        <p>{error.message}</p>
        <button data-testid="custom-reset" onClick={reset}>
          Reset
        </button>
      </div>
    ));

    render(
      <ErrorBoundary fallback={customFallback}>
        <BuggyComponent message="Render prop error" />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("render-fallback")).toBeInTheDocument();
    expect(screen.getByText("Render prop error")).toBeInTheDocument();
    expect(customFallback).toHaveBeenCalled();
    expect(customFallback).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ message: "Render prop error" }),
      expect.any(Function),
    );
  });

  test("fires onError callback with error and errorInfo", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    const onError = vi.fn();

    render(
      <ErrorBoundary onError={onError}>
        <BuggyComponent message="Callback test" />
      </ErrorBoundary>,
    );

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Callback test" }),
      expect.objectContaining({ componentStack: expect.any(String) }),
    );
  });

  test("retry resets error state and re-renders children", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    const { rerender } = render(
      <ErrorBoundary>
        <MaybeBuggy shouldThrow={true} />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("error-boundary-fallback")).toBeInTheDocument();

    rerender(
      <ErrorBoundary>
        <MaybeBuggy shouldThrow={false} />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("error-boundary-fallback")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("error-boundary-retry"));

    expect(screen.getByTestId("safe-child")).toHaveTextContent("Recovered");
    expect(
      screen.queryByTestId("error-boundary-fallback"),
    ).not.toBeInTheDocument();
  });

  test("retry re-catches error if child still throws", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    function AlwaysBuggy() {
      throw new Error("Always throws");
    }

    render(
      <ErrorBoundary>
        <AlwaysBuggy />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("error-boundary-fallback")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("error-boundary-retry"));

    expect(screen.getByTestId("error-boundary-fallback")).toBeInTheDocument();
  });

  test("resetKeys change triggers auto-reset and re-catches if child still throws", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    const { rerender } = render(
      <ErrorBoundary resetKeys={["initial"]}>
        <MaybeBuggy shouldThrow={true} />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("error-boundary-fallback")).toBeInTheDocument();

    rerender(
      <ErrorBoundary resetKeys={["updated"]}>
        <MaybeBuggy shouldThrow={true} />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("error-boundary-fallback")).toBeInTheDocument();
  });

  test("resetKeys change triggers auto-reset", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    const { rerender } = render(
      <ErrorBoundary resetKeys={["initial"]}>
        <MaybeBuggy shouldThrow={true} />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("error-boundary-fallback")).toBeInTheDocument();

    rerender(
      <ErrorBoundary resetKeys={["updated"]}>
        <MaybeBuggy shouldThrow={false} />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("safe-child")).toHaveTextContent("Recovered");
    expect(
      screen.queryByTestId("error-boundary-fallback"),
    ).not.toBeInTheDocument();
  });

  test("resetKeys transition undefined to array triggers reset", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    const { rerender } = render(
      <ErrorBoundary>
        <MaybeBuggy shouldThrow={true} />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("error-boundary-fallback")).toBeInTheDocument();

    rerender(
      <ErrorBoundary resetKeys={["key"]}>
        <MaybeBuggy shouldThrow={false} />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("safe-child")).toHaveTextContent("Recovered");
  });

  test("resetKeys transition array to undefined triggers reset", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    const { rerender } = render(
      <ErrorBoundary resetKeys={["key"]}>
        <MaybeBuggy shouldThrow={true} />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("error-boundary-fallback")).toBeInTheDocument();

    rerender(
      <ErrorBoundary>
        <MaybeBuggy shouldThrow={false} />
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("safe-child")).toHaveTextContent("Recovered");
  });

  test("onError is not called when no error occurs", () => {
    const onError = vi.fn();
    render(
      <ErrorBoundary onError={onError}>
        <SafeComponent />
      </ErrorBoundary>,
    );
    expect(onError).not.toHaveBeenCalled();
  });

  test("nested error boundaries - inner catches error, outer remains intact", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <div data-testid="outer-content">
          <ErrorBoundary>
            <BuggyComponent message="Inner error" />
          </ErrorBoundary>
        </div>
      </ErrorBoundary>,
    );

    expect(screen.getByTestId("outer-content")).toBeInTheDocument();
    expect(screen.getByTestId("error-boundary-fallback")).toBeInTheDocument();
  });
});
