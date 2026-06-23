import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

import {
  WebPreview,
  WebPreviewNavigation,
  WebPreviewNavigationButton,
  WebPreviewUrl,
  WebPreviewBody,
  WebPreviewConsole,
} from "@/components/ai-elements/web-preview";

afterEach(() => {
  cleanup();
});

describe("WebPreview", () => {
  test("renders with children", () => {
    render(
      <WebPreview data-testid="preview">
        <p>Preview content</p>
      </WebPreview>,
    );
    expect(screen.getByTestId("preview")).toBeInTheDocument();
    expect(screen.getByText("Preview content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <WebPreview className="custom-preview" data-testid="preview">
        <p>Content</p>
      </WebPreview>,
    );
    expect(screen.getByTestId("preview")).toHaveClass("custom-preview");
  });

  test("has rounded-lg and border classes", () => {
    render(
      <WebPreview data-testid="preview">
        <p>Content</p>
      </WebPreview>,
    );
    const el = screen.getByTestId("preview");
    expect(el.className).toContain("rounded-lg");
    expect(el.className).toContain("border");
    expect(el.className).toContain("flex");
    expect(el.className).toContain("flex-col");
  });

  test("provides web preview context to children", () => {
    render(
      <WebPreview data-testid="preview">
        <WebPreviewUrl data-testid="url-input" />
      </WebPreview>,
    );
    expect(screen.getByTestId("url-input")).toBeInTheDocument();
  });
});

describe("WebPreviewNavigation", () => {
  test("renders with children", () => {
    render(
      <WebPreview>
        <WebPreviewNavigation data-testid="nav">
          <button>Back</button>
          <button>Forward</button>
        </WebPreviewNavigation>
      </WebPreview>,
    );
    expect(screen.getByText("Back")).toBeInTheDocument();
    expect(screen.getByText("Forward")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <WebPreview>
        <WebPreviewNavigation className="custom-nav" data-testid="nav" />
      </WebPreview>,
    );
    expect(screen.getByTestId("nav")).toHaveClass("custom-nav");
  });

  test("has border-bottom and flex classes", () => {
    render(
      <WebPreview>
        <WebPreviewNavigation data-testid="nav" />
      </WebPreview>,
    );
    const el = screen.getByTestId("nav");
    expect(el.className).toContain("border-b");
    expect(el.className).toContain("flex");
    expect(el.className).toContain("items-center");
  });
});

describe("WebPreviewNavigationButton", () => {
  test("renders as a button", () => {
    render(
      <WebPreviewNavigationButton data-testid="nav-btn">
        <span>Button</span>
      </WebPreviewNavigationButton>,
    );
    const btn = screen.getByTestId("nav-btn");
    expect(btn.tagName).toBe("BUTTON");
  });

  test("renders with tooltip", () => {
    render(
      <WebPreviewNavigationButton tooltip="Go back" data-testid="nav-btn">
        <span>Back</span>
      </WebPreviewNavigationButton>,
    );
    expect(screen.getByText("Back")).toBeInTheDocument();
  });

  test("can be disabled", () => {
    render(
      <WebPreviewNavigationButton disabled data-testid="nav-btn">
        <span>Disabled</span>
      </WebPreviewNavigationButton>,
    );
    expect(screen.getByTestId("nav-btn")).toBeDisabled();
  });

  test("applies custom className", () => {
    render(
      <WebPreviewNavigationButton className="custom-btn" data-testid="nav-btn">
        <span>Btn</span>
      </WebPreviewNavigationButton>,
    );
    expect(screen.getByTestId("nav-btn")).toHaveClass("custom-btn");
  });

  test("calls onClick handler", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <WebPreviewNavigationButton onClick={onClick} data-testid="nav-btn">
        <span>Click me</span>
      </WebPreviewNavigationButton>,
    );
    await user.click(screen.getByTestId("nav-btn"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

describe("WebPreviewUrl", () => {
  test("renders an input element", () => {
    render(
      <WebPreview>
        <WebPreviewUrl data-testid="url-input" />
      </WebPreview>,
    );
    expect(screen.getByTestId("url-input")).toBeInTheDocument();
  });

  test("has placeholder text", () => {
    render(
      <WebPreview>
        <WebPreviewUrl data-testid="url-input" />
      </WebPreview>,
    );
    expect(screen.getByPlaceholderText("Enter URL...")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <WebPreview>
        <WebPreviewUrl className="custom-url" data-testid="url-input" />
      </WebPreview>,
    );
    expect(screen.getByTestId("url-input")).toHaveClass("custom-url");
  });

  test("syncs with context URL", () => {
    render(
      <WebPreview defaultUrl="https://example.com">
        <WebPreviewUrl data-testid="url-input" />
      </WebPreview>,
    );
    expect(screen.getByTestId("url-input")).toHaveValue("https://example.com");
  });

  test("updates context URL on Enter key", async () => {
    const user = userEvent.setup();
    const onUrlChange = vi.fn();
    render(
      <WebPreview onUrlChange={onUrlChange}>
        <WebPreviewUrl data-testid="url-input" />
      </WebPreview>,
    );

    const input = screen.getByTestId("url-input");
    await user.type(input, "https://new-url.com");
    await user.keyboard("{Enter}");

    expect(onUrlChange).toHaveBeenCalledWith("https://new-url.com");
  });
});

describe("WebPreviewBody", () => {
  test("renders an iframe", () => {
    render(
      <WebPreview>
        <WebPreviewBody data-testid="body" />
      </WebPreview>,
    );
    const iframe = screen.getByTitle("Preview");
    expect(iframe).toBeInTheDocument();
    expect(iframe.tagName).toBe("IFRAME");
  });

  test("sets sandbox attribute", () => {
    render(
      <WebPreview>
        <WebPreviewBody data-testid="body" />
      </WebPreview>,
    );
    const iframe = screen.getByTitle("Preview");
    expect(iframe).toHaveAttribute(
      "sandbox",
      "allow-scripts allow-same-origin allow-forms allow-popups allow-presentation",
    );
  });

  test("uses context URL as iframe src", () => {
    render(
      <WebPreview defaultUrl="https://example.com">
        <WebPreviewBody data-testid="body" />
      </WebPreview>,
    );
    const iframe = screen.getByTitle("Preview");
    expect(iframe).toHaveAttribute("src", "https://example.com");
  });

  test("uses src prop override over context URL", () => {
    render(
      <WebPreview defaultUrl="https://context.com">
        <WebPreviewBody src="https://override.com" data-testid="body" />
      </WebPreview>,
    );
    const iframe = screen.getByTitle("Preview");
    expect(iframe).toHaveAttribute("src", "https://override.com");
  });

  test("renders loading indicator when provided", () => {
    render(
      <WebPreview>
        <WebPreviewBody
          loading={<span data-testid="loading">Loading...</span>}
          data-testid="body"
        />
      </WebPreview>,
    );
    expect(screen.getByTestId("loading")).toBeInTheDocument();
  });

  test("applies custom className to iframe", () => {
    render(
      <WebPreview>
        <WebPreviewBody className="custom-iframe" data-testid="body" />
      </WebPreview>,
    );
    const iframe = screen.getByTitle("Preview");
    expect(iframe.className).toContain("custom-iframe");
  });
});

describe("WebPreviewConsole", () => {
  test("renders console header", () => {
    render(
      <WebPreview>
        <WebPreviewConsole data-testid="console" />
      </WebPreview>,
    );
    expect(screen.getByText("Console")).toBeInTheDocument();
  });

  test("shows 'No console output' when logs are empty", async () => {
    const user = userEvent.setup();
    render(
      <WebPreview>
        <WebPreviewConsole data-testid="console" />
      </WebPreview>,
    );

    // Click to expand the console
    await user.click(screen.getByText("Console"));

    expect(screen.getByText("No console output")).toBeInTheDocument();
  });

  test("renders log messages when expanded", async () => {
    const user = userEvent.setup();
    const logs = [
      {
        level: "log" as const,
        message: "Hello world",
        timestamp: new Date("2024-01-01T12:00:00"),
      },
      {
        level: "error" as const,
        message: "Something went wrong",
        timestamp: new Date("2024-01-01T12:01:00"),
      },
      {
        level: "warn" as const,
        message: "Warning message",
        timestamp: new Date("2024-01-01T12:02:00"),
      },
    ];

    render(
      <WebPreview>
        <WebPreviewConsole logs={logs} data-testid="console" />
      </WebPreview>,
    );

    // Click to expand
    await user.click(screen.getByText("Console"));

    expect(screen.getByText("Hello world")).toBeInTheDocument();
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("Warning message")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <WebPreview>
        <WebPreviewConsole className="custom-console" data-testid="console" />
      </WebPreview>,
    );
    expect(screen.getByTestId("console")).toHaveClass("custom-console");
  });

  test("renders children inside console", async () => {
    const user = userEvent.setup();
    render(
      <WebPreview>
        <WebPreviewConsole data-testid="console">
          <span data-testid="custom-log">Custom log entry</span>
        </WebPreviewConsole>
      </WebPreview>,
    );

    // Click to expand
    await user.click(screen.getByText("Console"));

    expect(screen.getByTestId("custom-log")).toBeInTheDocument();
  });
});

describe("WebPreview composition", () => {
  test("renders a full web preview layout", async () => {
    const user = userEvent.setup();
    render(
      <WebPreview defaultUrl="https://example.com" data-testid="preview">
        <WebPreviewNavigation>
          <WebPreviewNavigationButton tooltip="Refresh">
            <span>R</span>
          </WebPreviewNavigationButton>
          <WebPreviewUrl data-testid="url" />
        </WebPreviewNavigation>
        <WebPreviewBody data-testid="body" />
        <WebPreviewConsole data-testid="console" />
      </WebPreview>,
    );

    expect(screen.getByTestId("preview")).toBeInTheDocument();
    expect(screen.getByTestId("url")).toHaveValue("https://example.com");
    expect(screen.getByTitle("Preview")).toBeInTheDocument();
    expect(screen.getByText("Console")).toBeInTheDocument();
  });
});

describe("useWebPreview error", () => {
  test("throws when WebPreviewUrl used outside WebPreview context", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => {
      render(<WebPreviewUrl data-testid="url" />);
    }).toThrow("WebPreview components must be used within a WebPreview");
    spy.mockRestore();
  });
});
