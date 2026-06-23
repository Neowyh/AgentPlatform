import { render, screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

import {
  OpenIn,
  OpenInContent,
  OpenInItem,
  OpenInLabel,
  OpenInSeparator,
  OpenInTrigger,
  OpenInChatGPT,
  OpenInClaude,
  OpenInT3,
  OpenInScira,
  OpenInv0,
  OpenInCursor,
} from "@/components/ai-elements/open-in-chat";

afterEach(() => {
  cleanup();
});

describe("OpenIn", () => {
  test("provides query context to children", () => {
    render(
      <OpenIn query="hello world">
        <OpenInTrigger data-testid="trigger" />
      </OpenIn>,
    );
    expect(screen.getByTestId("trigger")).toBeInTheDocument();
  });
});

describe("OpenInTrigger", () => {
  test("renders default button text", () => {
    render(
      <OpenIn query="test">
        <OpenInTrigger data-testid="trigger" />
      </OpenIn>,
    );
    expect(screen.getByText("Open in chat")).toBeInTheDocument();
  });

  test("renders chevron icon", () => {
    render(
      <OpenIn query="test">
        <OpenInTrigger data-testid="trigger" />
      </OpenIn>,
    );
    const svg = screen.getByTestId("trigger").querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  test("renders custom children", () => {
    render(
      <OpenIn query="test">
        <OpenInTrigger data-testid="trigger">
          <span>Custom trigger</span>
        </OpenInTrigger>
      </OpenIn>,
    );
    expect(screen.getByText("Custom trigger")).toBeInTheDocument();
    expect(screen.queryByText("Open in chat")).not.toBeInTheDocument();
  });

  test("applies additional props", () => {
    render(
      <OpenIn query="test">
        <OpenInTrigger className="custom-trigger" data-testid="trigger" />
      </OpenIn>,
    );
    expect(screen.getByTestId("trigger")).toHaveClass("custom-trigger");
  });
});

describe("OpenInChatGPT", () => {
  test("renders ChatGPT link when dropdown is open", async () => {
    const user = userEvent.setup();
    render(
      <OpenIn query="hello world">
        <OpenInTrigger data-testid="trigger" />
        <OpenInContent>
          <OpenInChatGPT data-testid="chatgpt" />
        </OpenInContent>
      </OpenIn>,
    );

    await user.click(screen.getByTestId("trigger"));

    await waitFor(() => {
      expect(screen.getByText("Open in ChatGPT")).toBeInTheDocument();
    });

    // asChild means the <a> IS the rendered element
    const link = screen.getByTestId("chatgpt");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute(
      "href",
      expect.stringContaining("chatgpt.com"),
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });
});

describe("OpenInClaude", () => {
  test("renders Claude link when dropdown is open", async () => {
    const user = userEvent.setup();
    render(
      <OpenIn query="test query">
        <OpenInTrigger data-testid="trigger" />
        <OpenInContent>
          <OpenInClaude data-testid="claude" />
        </OpenInContent>
      </OpenIn>,
    );

    await user.click(screen.getByTestId("trigger"));

    await waitFor(() => {
      expect(screen.getByText("Open in Claude")).toBeInTheDocument();
    });

    const link = screen.getByTestId("claude");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", expect.stringContaining("claude.ai"));
    expect(link).toHaveAttribute("target", "_blank");
  });
});

describe("OpenInT3", () => {
  test("renders T3 Chat link when dropdown is open", async () => {
    const user = userEvent.setup();
    render(
      <OpenIn query="test">
        <OpenInTrigger data-testid="trigger" />
        <OpenInContent>
          <OpenInT3 data-testid="t3" />
        </OpenInContent>
      </OpenIn>,
    );

    await user.click(screen.getByTestId("trigger"));

    await waitFor(() => {
      expect(screen.getByText("Open in T3 Chat")).toBeInTheDocument();
    });

    const link = screen.getByTestId("t3");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", expect.stringContaining("t3.chat"));
    expect(link).toHaveAttribute("target", "_blank");
  });
});

describe("OpenInScira", () => {
  test("renders Scira link when dropdown is open", async () => {
    const user = userEvent.setup();
    render(
      <OpenIn query="search term">
        <OpenInTrigger data-testid="trigger" />
        <OpenInContent>
          <OpenInScira data-testid="scira" />
        </OpenInContent>
      </OpenIn>,
    );

    await user.click(screen.getByTestId("trigger"));

    await waitFor(() => {
      expect(screen.getByText("Open in Scira")).toBeInTheDocument();
    });

    const link = screen.getByTestId("scira");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", expect.stringContaining("scira.ai"));
    expect(link).toHaveAttribute("target", "_blank");
  });
});

describe("OpenInv0", () => {
  test("renders v0 link when dropdown is open", async () => {
    const user = userEvent.setup();
    render(
      <OpenIn query="build a form">
        <OpenInTrigger data-testid="trigger" />
        <OpenInContent>
          <OpenInv0 data-testid="v0" />
        </OpenInContent>
      </OpenIn>,
    );

    await user.click(screen.getByTestId("trigger"));

    await waitFor(() => {
      expect(screen.getByText("Open in v0")).toBeInTheDocument();
    });

    const link = screen.getByTestId("v0");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", expect.stringContaining("v0.app"));
    expect(link).toHaveAttribute("target", "_blank");
  });
});

describe("OpenInCursor", () => {
  test("renders Cursor link when dropdown is open", async () => {
    const user = userEvent.setup();
    render(
      <OpenIn query="refactor code">
        <OpenInTrigger data-testid="trigger" />
        <OpenInContent>
          <OpenInCursor data-testid="cursor" />
        </OpenInContent>
      </OpenIn>,
    );

    await user.click(screen.getByTestId("trigger"));

    await waitFor(() => {
      expect(screen.getByText("Open in Cursor")).toBeInTheDocument();
    });

    const link = screen.getByTestId("cursor");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", expect.stringContaining("cursor.com"));
    expect(link).toHaveAttribute("target", "_blank");
  });
});

describe("OpenIn composition", () => {
  test("renders a full open-in menu when triggered", async () => {
    const user = userEvent.setup();
    render(
      <OpenIn query="test query">
        <OpenInTrigger data-testid="trigger" />
        <OpenInContent data-testid="content">
          <OpenInLabel>AI Services</OpenInLabel>
          <OpenInChatGPT data-testid="chatgpt" />
          <OpenInClaude data-testid="claude" />
          <OpenInSeparator />
          <OpenInT3 data-testid="t3" />
          <OpenInScira data-testid="scira" />
          <OpenInv0 data-testid="v0" />
          <OpenInCursor data-testid="cursor" />
        </OpenInContent>
      </OpenIn>,
    );

    // Open the dropdown
    await user.click(screen.getByTestId("trigger"));

    await waitFor(() => {
      expect(screen.getByText("AI Services")).toBeInTheDocument();
    });

    expect(screen.getByText("Open in ChatGPT")).toBeInTheDocument();
    expect(screen.getByText("Open in Claude")).toBeInTheDocument();
    expect(screen.getByText("Open in T3 Chat")).toBeInTheDocument();
    expect(screen.getByText("Open in Scira")).toBeInTheDocument();
    expect(screen.getByText("Open in v0")).toBeInTheDocument();
    expect(screen.getByText("Open in Cursor")).toBeInTheDocument();
  });

  test("each link opens in a new tab", async () => {
    const user = userEvent.setup();
    render(
      <OpenIn query="test">
        <OpenInTrigger data-testid="trigger" />
        <OpenInContent>
          <OpenInChatGPT data-testid="chatgpt" />
          <OpenInClaude data-testid="claude" />
          <OpenInT3 data-testid="t3" />
          <OpenInScira data-testid="scira" />
          <OpenInv0 data-testid="v0" />
          <OpenInCursor data-testid="cursor" />
        </OpenInContent>
      </OpenIn>,
    );

    await user.click(screen.getByTestId("trigger"));

    await waitFor(() => {
      expect(screen.getByText("Open in ChatGPT")).toBeInTheDocument();
    });

    const items = ["chatgpt", "claude", "t3", "scira", "v0", "cursor"];

    for (const id of items) {
      const link = screen.getByTestId(id);
      expect(link.tagName).toBe("A");
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
    }
  });
});

describe("OpenInItem", () => {
  test("renders as a dropdown menu item", async () => {
    const user = userEvent.setup();
    render(
      <OpenIn query="test">
        <OpenInTrigger data-testid="trigger" />
        <OpenInContent>
          <OpenInItem data-testid="item">Custom Item</OpenInItem>
        </OpenInContent>
      </OpenIn>,
    );

    await user.click(screen.getByTestId("trigger"));

    await waitFor(() => {
      expect(screen.getByText("Custom Item")).toBeInTheDocument();
    });
  });
});

describe("OpenIn context error", () => {
  test("throws when provider component used outside OpenIn", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => {
      render(<OpenInChatGPT data-testid="chatgpt" />);
    }).toThrow("OpenIn components must be used within an OpenIn provider");

    spy.mockRestore();
  });
});
