import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      scenarios: {
        daily: "日常办公",
        creative: "创意设计",
        professional: "专业任务",
      },
    },
  }),
}));

import { ScenarioTabs } from "@/components/workspace/scenario/scenario-tabs";

afterEach(() => {
  cleanup();
});

describe("ScenarioTabs", () => {
  const defaultProps = {
    selected: null as "daily" | "creative" | "professional" | null,
    onSelect: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders 3 tabs (日常办公、创意设计、专业任务)", () => {
    render(<ScenarioTabs {...defaultProps} />);
    expect(screen.getByRole("tab", { name: /日常办公/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /创意设计/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /专业任务/ })).toBeInTheDocument();
    expect(screen.getByTestId("scenario-tabs")).toBeInTheDocument();
  });

  it("clicks tab → onSelect called with id", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<ScenarioTabs {...defaultProps} onSelect={onSelect} />);

    await user.click(screen.getByRole("tab", { name: /日常办公/ }));
    expect(onSelect).toHaveBeenCalledWith("daily");
  });

  it("clicks same tab again → keeps the tab selected", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<ScenarioTabs selected="daily" onSelect={onSelect} />);

    await user.click(screen.getByRole("tab", { name: /日常办公/ }));
    expect(onSelect).toHaveBeenCalledWith("daily");
  });

  it("ArrowRight cycles to next tab", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<ScenarioTabs selected="daily" onSelect={onSelect} />);

    const tab = screen.getByRole("tab", { name: /日常办公/ });
    tab.focus();
    await user.keyboard("{ArrowRight}");
    expect(onSelect).toHaveBeenCalledWith("creative");
  });

  it("ArrowLeft cycles to previous tab", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<ScenarioTabs selected="daily" onSelect={onSelect} />);

    const tab = screen.getByRole("tab", { name: /日常办公/ });
    tab.focus();
    await user.keyboard("{ArrowLeft}");
    expect(onSelect).toHaveBeenCalledWith("professional");
  });

  it("Home key jumps to first tab", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<ScenarioTabs selected="professional" onSelect={onSelect} />);

    const tab = screen.getByRole("tab", { name: /专业任务/ });
    tab.focus();
    await user.keyboard("{Home}");
    expect(onSelect).toHaveBeenCalledWith("daily");
  });

  it("End key jumps to last tab", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<ScenarioTabs selected="daily" onSelect={onSelect} />);

    const tab = screen.getByRole("tab", { name: /日常办公/ });
    tab.focus();
    await user.keyboard("{End}");
    expect(onSelect).toHaveBeenCalledWith("professional");
  });

  it("selected=null → all tabs have tabIndex=-1 (none active)", () => {
    render(<ScenarioTabs {...defaultProps} />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs[0]).toHaveAttribute("tabindex", "-1");
    expect(tabs[1]).toHaveAttribute("tabindex", "-1");
    expect(tabs[2]).toHaveAttribute("tabindex", "-1");
  });

  it("selected tab has aria-selected=true and data-state=active", () => {
    render(<ScenarioTabs selected="creative" onSelect={vi.fn()} />);
    const creativeTab = screen.getByRole("tab", { name: /创意设计/ });
    expect(creativeTab).toHaveAttribute("aria-selected", "true");
    expect(creativeTab).toHaveAttribute("data-state", "active");

    const dailyTab = screen.getByRole("tab", { name: /日常办公/ });
    expect(dailyTab).toHaveAttribute("aria-selected", "false");
    expect(dailyTab).toHaveAttribute("data-state", "inactive");
  });

  it("active tab has font-semibold class", () => {
    render(<ScenarioTabs selected="daily" onSelect={vi.fn()} />);
    const activeTab = screen.getByRole("tab", { name: /日常办公/ });
    expect(activeTab.className).toContain("font-semibold");
  });

  it("active tab has bg-muted class (not bg-muted/60)", () => {
    render(<ScenarioTabs selected="daily" onSelect={vi.fn()} />);
    const activeTab = screen.getByRole("tab", { name: /日常办公/ });
    expect(activeTab.className).toContain("bg-muted");
    expect(activeTab.className).not.toContain("bg-muted/60");
  });

  it("non-active tab has hover:bg-muted/60 class", () => {
    render(<ScenarioTabs selected="daily" onSelect={vi.fn()} />);
    const inactiveTab = screen.getByRole("tab", { name: /创意设计/ });
    expect(inactiveTab.className).toContain("hover:bg-muted/60");
  });

  it("tab renders icon (svg) and label text", () => {
    render(<ScenarioTabs selected={null} onSelect={vi.fn()} />);
    const dailyTab = screen.getByRole("tab", { name: /日常办公/ });
    expect(dailyTab.querySelector("svg")).toBeInTheDocument();
    expect(dailyTab.textContent).toContain("日常办公");
  });
});
