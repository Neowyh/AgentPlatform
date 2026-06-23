import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

// ── Mocks ────────────────────────────────────────────────────────────────────

let mockSetSidebarOpen: ReturnType<typeof vi.fn>;

vi.mock("@/components/ui/sidebar", () => ({
  useSidebar: () => ({
    open: true,
    setOpen: mockSetSidebarOpen,
  }),
}));

vi.mock("@/env", () => ({
  env: {
    NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false",
  },
}));

// ── Dynamic import ───────────────────────────────────────────────────────────

import {
  ArtifactsProvider,
  useArtifacts,
} from "@/components/workspace/artifacts/context";

beforeEach(async () => {
  vi.clearAllMocks();
  mockSetSidebarOpen = vi.fn();
});

afterEach(() => {
  cleanup();
});

// ── Helper component ─────────────────────────────────────────────────────────

function TestConsumer() {
  const ctx = useArtifacts();
  return (
    <div>
      <span data-testid="artifacts">{JSON.stringify(ctx.artifacts)}</span>
      <span data-testid="selected">{ctx.selectedArtifact}</span>
      <span data-testid="open">{String(ctx.open)}</span>
      <span data-testid="auto-select">{String(ctx.autoSelect)}</span>
      <span data-testid="auto-open">{String(ctx.autoOpen)}</span>
      <button data-testid="select-btn" onClick={() => ctx.select("file-1")} />
      <button
        data-testid="select-auto-btn"
        onClick={() => ctx.select("file-2", true)}
      />
      <button data-testid="deselect-btn" onClick={() => ctx.deselect()} />
      <button data-testid="set-open-btn" onClick={() => ctx.setOpen(true)} />
      <button data-testid="set-close-btn" onClick={() => ctx.setOpen(false)} />
      <button
        data-testid="set-artifacts-btn"
        onClick={() => ctx.setArtifacts(["a.txt", "b.txt"])}
      />
    </div>
  );
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("ArtifactsProvider", () => {
  test("provides default context values", () => {
    render(
      <ArtifactsProvider>
        <TestConsumer />
      </ArtifactsProvider>,
    );
    expect(screen.getByTestId("artifacts")).toHaveTextContent("[]");
    expect(screen.getByTestId("selected")).toHaveTextContent("");
    expect(screen.getByTestId("open")).toHaveTextContent("false");
    expect(screen.getByTestId("auto-select")).toHaveTextContent("true");
    expect(screen.getByTestId("auto-open")).toHaveTextContent("true");
  });

  test("select sets selectedArtifact and closes sidebar", () => {
    render(
      <ArtifactsProvider>
        <TestConsumer />
      </ArtifactsProvider>,
    );
    fireEvent.click(screen.getByTestId("select-btn"));
    expect(screen.getByTestId("selected")).toHaveTextContent("file-1");
    expect(mockSetSidebarOpen).toHaveBeenCalledWith(false);
  });

  test("select with autoSelect=true does not change autoSelect", () => {
    render(
      <ArtifactsProvider>
        <TestConsumer />
      </ArtifactsProvider>,
    );
    fireEvent.click(screen.getByTestId("select-auto-btn"));
    expect(screen.getByTestId("selected")).toHaveTextContent("file-2");
    // autoSelect stays true when autoSelect param is true
    expect(screen.getByTestId("auto-select")).toHaveTextContent("true");
  });

  test("select with autoSelect=false (default) sets autoSelect to false", () => {
    render(
      <ArtifactsProvider>
        <TestConsumer />
      </ArtifactsProvider>,
    );
    fireEvent.click(screen.getByTestId("select-btn"));
    expect(screen.getByTestId("auto-select")).toHaveTextContent("false");
  });

  test("deselect clears selectedArtifact and resets state", () => {
    render(
      <ArtifactsProvider>
        <TestConsumer />
      </ArtifactsProvider>,
    );
    // First select
    fireEvent.click(screen.getByTestId("select-btn"));
    expect(screen.getByTestId("selected")).toHaveTextContent("file-1");

    // Then deselect
    fireEvent.click(screen.getByTestId("deselect-btn"));
    expect(screen.getByTestId("selected")).toHaveTextContent("");
    expect(screen.getByTestId("auto-select")).toHaveTextContent("true");
    expect(screen.getByTestId("open")).toHaveTextContent("false");
  });

  test("setOpen(true) sets open to true", () => {
    render(
      <ArtifactsProvider>
        <TestConsumer />
      </ArtifactsProvider>,
    );
    fireEvent.click(screen.getByTestId("set-open-btn"));
    expect(screen.getByTestId("open")).toHaveTextContent("true");
  });

  test("setOpen(false) sets open to false and resets autoOpen/autoSelect", () => {
    render(
      <ArtifactsProvider>
        <TestConsumer />
      </ArtifactsProvider>,
    );
    fireEvent.click(screen.getByTestId("set-close-btn"));
    expect(screen.getByTestId("open")).toHaveTextContent("false");
    expect(screen.getByTestId("auto-open")).toHaveTextContent("false");
    expect(screen.getByTestId("auto-select")).toHaveTextContent("false");
  });

  test("setArtifacts updates the artifacts list", () => {
    render(
      <ArtifactsProvider>
        <TestConsumer />
      </ArtifactsProvider>,
    );
    fireEvent.click(screen.getByTestId("set-artifacts-btn"));
    expect(screen.getByTestId("artifacts")).toHaveTextContent(
      '["a.txt","b.txt"]',
    );
  });

  test("throws when useArtifacts is used outside provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    function BadConsumer() {
      useArtifacts();
      return null;
    }

    expect(() => render(<BadConsumer />)).toThrow(
      "useArtifacts must be used within an ArtifactsProvider",
    );

    spy.mockRestore();
  });
});
