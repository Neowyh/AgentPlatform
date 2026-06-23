import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/components/ui/sidebar", () => ({
  useSidebar: () => ({ setOpen: vi.fn() }),
}));

vi.mock("@/env", () => ({
  env: { NEXT_PUBLIC_STATIC_WEBSITE_ONLY: "false" },
}));

import {
  ArtifactsProvider,
  useArtifacts,
} from "@/components/workspace/artifacts/context";

afterEach(() => {
  cleanup();
});

function TestConsumer() {
  const ctx = useArtifacts();
  return (
    <div>
      <span data-testid="count">{ctx.artifacts.length}</span>
      <span data-testid="selected">{String(ctx.selectedArtifact)}</span>
      <span data-testid="open">{String(ctx.open)}</span>
      <button onClick={() => ctx.setArtifacts(["a.tsx", "b.tsx"])}>set</button>
      <button onClick={() => ctx.select("a.tsx")}>select</button>
      <button onClick={() => ctx.deselect()}>deselect</button>
      <button onClick={() => ctx.setOpen(true)}>open</button>
    </div>
  );
}

describe("ArtifactsProvider", () => {
  test("provides default context values", () => {
    render(
      <ArtifactsProvider>
        <TestConsumer />
      </ArtifactsProvider>,
    );
    expect(screen.getByTestId("count")).toHaveTextContent("0");
    expect(screen.getByTestId("selected")).toHaveTextContent("null");
  });

  test("setArtifacts updates artifacts list", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(
      <ArtifactsProvider>
        <TestConsumer />
      </ArtifactsProvider>,
    );
    await user.click(screen.getByText("set"));
    expect(screen.getByTestId("count")).toHaveTextContent("2");
  });

  test("select sets selectedArtifact", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(
      <ArtifactsProvider>
        <TestConsumer />
      </ArtifactsProvider>,
    );
    await user.click(screen.getByText("select"));
    expect(screen.getByTestId("selected")).toHaveTextContent("a.tsx");
  });

  test("deselect clears selectedArtifact", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(
      <ArtifactsProvider>
        <TestConsumer />
      </ArtifactsProvider>,
    );
    await user.click(screen.getByText("select"));
    await user.click(screen.getByText("deselect"));
    expect(screen.getByTestId("selected")).toHaveTextContent("null");
  });
});

describe("useArtifacts", () => {
  test("throws when used outside provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    function Bad() {
      useArtifacts();
      return null;
    }
    expect(() => render(<Bad />)).toThrow(
      "useArtifacts must be used within an ArtifactsProvider",
    );
    spy.mockRestore();
  });
});
