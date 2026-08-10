import { render, screen, act, cleanup } from "@testing-library/react";
import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";

import { I18nProvider, useI18nContext, I18nContext } from "@/core/i18n/context";

// Helper component to test the context hook
function LocaleDisplay() {
  const { locale, setLocale } = useI18nContext();
  return (
    <div>
      <span data-testid="locale">{locale}</span>
      <button data-testid="change-locale" onClick={() => setLocale("zh-CN")}>
        Change Locale
      </button>
    </div>
  );
}

describe("I18nContext", () => {
  it("creates a context with null default", () => {
    expect(I18nContext).toBeDefined();
    expect(I18nContext.Provider).toBeDefined();
  });
});

describe("I18nProvider", () => {
  const originalCookieDescriptor = Object.getOwnPropertyDescriptor(
    Document.prototype,
    "cookie",
  );

  beforeEach(() => {
    cleanup();
  });

  afterEach(() => {
    cleanup();
    // Restore original cookie descriptor
    if (originalCookieDescriptor) {
      Object.defineProperty(
        Document.prototype,
        "cookie",
        originalCookieDescriptor,
      );
    }
  });

  it("renders children", () => {
    render(
      <I18nProvider initialLocale="en-US">
        <div>Child content</div>
      </I18nProvider>,
    );

    expect(screen.getByText("Child content")).toBeDefined();
  });

  it("provides the initial locale via context", () => {
    render(
      <I18nProvider initialLocale="en-US">
        <LocaleDisplay />
      </I18nProvider>,
    );

    expect(screen.getByTestId("locale").textContent).toBe("en-US");
  });

  it("provides zh-CN when set as initial locale", () => {
    render(
      <I18nProvider initialLocale="zh-CN">
        <LocaleDisplay />
      </I18nProvider>,
    );

    expect(screen.getByTestId("locale").textContent).toBe("zh-CN");
  });

  it("normalizes a short locale cookie on mount", () => {
    let cookieValue = "locale=zh";
    Object.defineProperty(Document.prototype, "cookie", {
      get() {
        return cookieValue;
      },
      set(value: string) {
        cookieValue = value;
      },
      configurable: true,
    });

    render(
      <I18nProvider initialLocale="zh-CN">
        <LocaleDisplay />
      </I18nProvider>,
    );

    expect(cookieValue).toContain("locale=zh-CN");
  });

  it("updates locale and sets cookie when setLocale is called", () => {
    let cookieValue = "";
    Object.defineProperty(Document.prototype, "cookie", {
      get() {
        return cookieValue;
      },
      set(value: string) {
        cookieValue = value;
      },
      configurable: true,
    });

    render(
      <I18nProvider initialLocale="en-US">
        <LocaleDisplay />
      </I18nProvider>,
    );

    expect(screen.getByTestId("locale").textContent).toBe("en-US");

    act(() => {
      screen.getByTestId("change-locale").click();
    });

    expect(screen.getByTestId("locale").textContent).toBe("zh-CN");
    expect(cookieValue).toContain("locale=zh-CN");
    expect(cookieValue).toContain("path=/");
    expect(cookieValue).toContain("max-age=31536000");
  });
});

describe("useI18nContext", () => {
  beforeEach(() => {
    cleanup();
  });

  it("throws error when used outside I18nProvider", () => {
    // Suppress console.error for expected error
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => {
      render(<LocaleDisplay />);
    }).toThrow("useI18n must be used within I18nProvider");

    consoleSpy.mockRestore();
  });

  it("returns context value when used inside I18nProvider", () => {
    let contextValue: ReturnType<typeof useI18nContext> | null = null;

    function CaptureContext() {
      contextValue = useI18nContext();
      return null;
    }

    render(
      <I18nProvider initialLocale="zh-CN">
        <CaptureContext />
      </I18nProvider>,
    );

    expect(contextValue).not.toBeNull();
    expect(contextValue!.locale).toBe("zh-CN");
    expect(typeof contextValue!.setLocale).toBe("function");
  });
});
