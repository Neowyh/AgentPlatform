import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, test, vi } from "vitest";

// Mock ResizeObserver and scrollIntoView for cmdk
beforeAll(() => {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;

  // Mock scrollIntoView for cmdk
  Element.prototype.scrollIntoView = vi.fn();
});

import {
  ModelSelector,
  ModelSelectorTrigger,
  ModelSelectorContent,
  ModelSelectorInput,
  ModelSelectorList,
  ModelSelectorEmpty,
  ModelSelectorGroup,
  ModelSelectorItem,
  ModelSelectorShortcut,
  ModelSelectorSeparator,
  ModelSelectorLogo,
  ModelSelectorLogoGroup,
  ModelSelectorName,
  ModelSelectorDialog,
} from "@/components/ai-elements/model-selector";

afterEach(() => {
  cleanup();
});

describe("ModelSelector", () => {
  test("renders as a dialog wrapper", () => {
    // ModelSelector wraps Dialog - it only renders children
    render(
      <ModelSelector open>
        <ModelSelectorContent data-testid="content">
          <p>Content body</p>
        </ModelSelectorContent>
      </ModelSelector>,
    );
    expect(screen.getByText("Content body")).toBeInTheDocument();
  });
});

describe("ModelSelectorTrigger", () => {
  test("renders as a dialog trigger", () => {
    render(
      <ModelSelector>
        <ModelSelectorTrigger data-testid="trigger">
          <button>Open</button>
        </ModelSelectorTrigger>
        <ModelSelectorContent>
          <p>Content</p>
        </ModelSelectorContent>
      </ModelSelector>,
    );
    expect(screen.getByTestId("trigger")).toBeInTheDocument();
  });
});

describe("ModelSelectorDialog", () => {
  test("renders as a command dialog", () => {
    render(
      <ModelSelectorDialog open>
        <p>Dialog content</p>
      </ModelSelectorDialog>,
    );
    expect(screen.getByText("Dialog content")).toBeInTheDocument();
  });
});

describe("ModelSelectorContent", () => {
  test("renders children when dialog is open", () => {
    render(
      <ModelSelector open>
        <ModelSelectorContent data-testid="content">
          <p>Content body</p>
        </ModelSelectorContent>
      </ModelSelector>,
    );
    expect(screen.getByText("Content body")).toBeInTheDocument();
  });

  test("renders default title as sr-only", () => {
    render(
      <ModelSelector open>
        <ModelSelectorContent data-testid="content" />
      </ModelSelector>,
    );
    expect(
      screen.getByText("Model Selector", { selector: ".sr-only" }),
    ).toBeInTheDocument();
  });

  test("renders custom title", () => {
    render(
      <ModelSelector open>
        <ModelSelectorContent title="Choose Model" data-testid="content" />
      </ModelSelector>,
    );
    expect(
      screen.getByText("Choose Model", { selector: ".sr-only" }),
    ).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <ModelSelector open>
        <ModelSelectorContent
          className="custom-content"
          data-testid="content"
        />
      </ModelSelector>,
    );
    expect(screen.getByTestId("content")).toHaveClass("custom-content");
  });
});

describe("ModelSelectorInput", () => {
  test("renders an input element when dialog is open", () => {
    render(
      <ModelSelector open>
        <ModelSelectorContent>
          <ModelSelectorInput data-testid="input" />
        </ModelSelectorContent>
      </ModelSelector>,
    );
    expect(screen.getByTestId("input")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <ModelSelector open>
        <ModelSelectorContent>
          <ModelSelectorInput className="custom-input" data-testid="input" />
        </ModelSelectorContent>
      </ModelSelector>,
    );
    expect(screen.getByTestId("input")).toHaveClass("custom-input");
  });
});

describe("ModelSelectorList", () => {
  test("renders children", () => {
    render(
      <ModelSelector open>
        <ModelSelectorContent>
          <ModelSelectorList data-testid="list">
            <p>List items</p>
          </ModelSelectorList>
        </ModelSelectorContent>
      </ModelSelector>,
    );
    expect(screen.getByText("List items")).toBeInTheDocument();
  });
});

describe("ModelSelectorEmpty", () => {
  test("renders empty state message", () => {
    render(
      <ModelSelector open>
        <ModelSelectorContent>
          <ModelSelectorEmpty data-testid="empty">
            No results found
          </ModelSelectorEmpty>
        </ModelSelectorContent>
      </ModelSelector>,
    );
    expect(screen.getByText("No results found")).toBeInTheDocument();
  });
});

describe("ModelSelectorGroup", () => {
  test("renders group with children", () => {
    render(
      <ModelSelector open>
        <ModelSelectorContent>
          <ModelSelectorGroup data-testid="group">
            <p>Group items</p>
          </ModelSelectorGroup>
        </ModelSelectorContent>
      </ModelSelector>,
    );
    expect(screen.getByText("Group items")).toBeInTheDocument();
  });
});

describe("ModelSelectorItem", () => {
  test("renders item with children", () => {
    render(
      <ModelSelector open>
        <ModelSelectorContent>
          <ModelSelectorList>
            <ModelSelectorItem data-testid="item">GPT-4</ModelSelectorItem>
          </ModelSelectorList>
        </ModelSelectorContent>
      </ModelSelector>,
    );
    expect(screen.getByText("GPT-4")).toBeInTheDocument();
  });
});

describe("ModelSelectorShortcut", () => {
  test("renders shortcut text", () => {
    render(
      <ModelSelectorShortcut data-testid="shortcut">
        Ctrl+K
      </ModelSelectorShortcut>,
    );
    expect(screen.getByText("Ctrl+K")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <ModelSelectorShortcut className="custom-shortcut" data-testid="shortcut">
        Cmd+K
      </ModelSelectorShortcut>,
    );
    expect(screen.getByTestId("shortcut")).toHaveClass("custom-shortcut");
  });
});

// ModelSelectorSeparator requires Command context (tested in composition test)

describe("ModelSelectorLogo", () => {
  test("renders an img element with provider logo", () => {
    render(<ModelSelectorLogo provider="openai" data-testid="logo" />);
    const img = screen.getByTestId("logo");
    expect(img.tagName).toBe("IMG");
    expect(img).toHaveAttribute("src", "https://models.dev/logos/openai.svg");
    expect(img).toHaveAttribute("alt", "openai logo");
  });

  test("applies custom className", () => {
    render(
      <ModelSelectorLogo
        provider="anthropic"
        className="custom-logo"
        data-testid="logo"
      />,
    );
    expect(screen.getByTestId("logo")).toHaveClass("custom-logo");
  });

  test("has fixed dimensions", () => {
    render(<ModelSelectorLogo provider="google" data-testid="logo" />);
    const img = screen.getByTestId("logo");
    expect(img).toHaveAttribute("width", "12");
    expect(img).toHaveAttribute("height", "12");
  });

  test("falls back to initial letter on image error", async () => {
    render(<ModelSelectorLogo provider="test-provider" data-testid="logo" />);
    const img = screen.getByTestId("logo");

    // Simulate image error
    fireEvent.error(img);

    // After error, should show fallback span
    await new Promise((r) => setTimeout(r, 0));
    const fallback = screen.getByLabelText("test-provider logo fallback");
    expect(fallback).toBeInTheDocument();
    expect(fallback).toHaveTextContent("t");
  });
});

describe("ModelSelectorLogoGroup", () => {
  test("renders with children", () => {
    render(
      <ModelSelectorLogoGroup data-testid="logo-group">
        <span>Logo 1</span>
        <span>Logo 2</span>
      </ModelSelectorLogoGroup>,
    );
    expect(screen.getByText("Logo 1")).toBeInTheDocument();
    expect(screen.getByText("Logo 2")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <ModelSelectorLogoGroup
        className="custom-group"
        data-testid="logo-group"
      />,
    );
    expect(screen.getByTestId("logo-group")).toHaveClass("custom-group");
  });

  test("has flex and shrink-0 classes", () => {
    render(
      <ModelSelectorLogoGroup data-testid="logo-group">
        <span>Logo</span>
      </ModelSelectorLogoGroup>,
    );
    const el = screen.getByTestId("logo-group");
    expect(el.className).toContain("flex");
    expect(el.className).toContain("shrink-0");
  });
});

describe("ModelSelectorName", () => {
  test("renders children text", () => {
    render(
      <ModelSelectorName data-testid="name">
        Claude 3.5 Sonnet
      </ModelSelectorName>,
    );
    expect(screen.getByText("Claude 3.5 Sonnet")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <ModelSelectorName className="custom-name" data-testid="name">
        Model
      </ModelSelectorName>,
    );
    expect(screen.getByTestId("name")).toHaveClass("custom-name");
  });

  test("has truncate and body text classes", () => {
    render(<ModelSelectorName data-testid="name">Model</ModelSelectorName>);
    const el = screen.getByTestId("name");
    expect(el.className).toContain("truncate");
    expect(el.className).toContain("text-base");
  });
});

describe("ModelSelector composition", () => {
  test("renders a full model selector layout", () => {
    render(
      <ModelSelector open>
        <ModelSelectorContent title="Select a model" data-testid="content">
          <ModelSelectorInput data-testid="input" />
          <ModelSelectorList data-testid="list">
            <ModelSelectorGroup data-testid="group">
              <ModelSelectorItem data-testid="item-1">GPT-4</ModelSelectorItem>
              <ModelSelectorItem data-testid="item-2">
                Claude 3.5
              </ModelSelectorItem>
            </ModelSelectorGroup>
            <ModelSelectorSeparator data-testid="separator" />
            <ModelSelectorEmpty data-testid="empty">
              No models found
            </ModelSelectorEmpty>
          </ModelSelectorList>
        </ModelSelectorContent>
      </ModelSelector>,
    );

    expect(
      screen.getByText("Select a model", { selector: ".sr-only" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("input")).toBeInTheDocument();
    expect(screen.getByText("GPT-4")).toBeInTheDocument();
    expect(screen.getByText("Claude 3.5")).toBeInTheDocument();
  });
});
