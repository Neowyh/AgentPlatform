import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import {
  BrowserViewProvider,
  useBrowserView,
  type BrowserViewFrame,
} from "@/components/workspace/browser-view/context";

function frameOf(overrides?: Partial<BrowserViewFrame>): BrowserViewFrame {
  return { screenshot: "shot-1.png", ...overrides };
}

function TestConsumer() {
  const browserView = useBrowserView();
  return (
    <div>
      <span data-testid="open">{String(browserView.open)}</span>
      <span data-testid="latest-frame">
        {browserView.latestFrame?.screenshot ?? "none"}
      </span>
      <button
        data-testid="push-frame"
        onClick={() =>
          browserView.pushFrame(frameOf({ screenshot: "shot-2.png" }))
        }
      />
      <button
        data-testid="push-same-frame"
        onClick={() => browserView.pushFrame(frameOf())}
      />
      <button
        data-testid="open-panel"
        onClick={() => browserView.openPanel()}
      />
      <button data-testid="close" onClick={() => browserView.close()} />
    </div>
  );
}

afterEach(() => {
  cleanup();
});

describe("BrowserViewProvider", () => {
  test("pushing a frame records it without opening the panel", () => {
    render(
      <BrowserViewProvider>
        <TestConsumer />
      </BrowserViewProvider>,
    );
    expect(screen.getByTestId("open")).toHaveTextContent("false");
    expect(screen.getByTestId("latest-frame")).toHaveTextContent("none");

    fireEvent.click(screen.getByTestId("push-frame"));

    expect(screen.getByTestId("latest-frame")).toHaveTextContent("shot-2.png");
    expect(screen.getByTestId("open")).toHaveTextContent("false");
  });

  test("pushing the same frame keeps the previous frame", () => {
    render(
      <BrowserViewProvider>
        <TestConsumer />
      </BrowserViewProvider>,
    );
    fireEvent.click(screen.getByTestId("push-same-frame"));
    fireEvent.click(screen.getByTestId("push-same-frame"));

    expect(screen.getByTestId("latest-frame")).toHaveTextContent("shot-1.png");
    expect(screen.getByTestId("open")).toHaveTextContent("false");
  });

  test("openPanel and close control the panel explicitly", () => {
    render(
      <BrowserViewProvider>
        <TestConsumer />
      </BrowserViewProvider>,
    );
    fireEvent.click(screen.getByTestId("open-panel"));
    expect(screen.getByTestId("open")).toHaveTextContent("true");

    fireEvent.click(screen.getByTestId("close"));
    expect(screen.getByTestId("open")).toHaveTextContent("false");
  });
});
