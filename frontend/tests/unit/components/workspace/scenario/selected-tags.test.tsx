import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, describe, it, expect, afterEach } from "vitest";

import {
  InlineSelectedTag,
  SelectedTags,
} from "@/components/workspace/scenario/selected-tags";
import type { SelectedTag } from "@/components/workspace/scenario/selected-tags";

afterEach(() => {
  cleanup();
});

const makeTag = (overrides: Partial<SelectedTag> = {}): SelectedTag => ({
  id: "tag-1",
  label: "Test Tag",
  ...overrides,
});

// ── SelectedTags ─────────────────────────────────────────────────────────────

describe("SelectedTags", () => {
  it("renders null when tags array is empty", () => {
    const { container } = render(<SelectedTags tags={[]} onRemove={vi.fn()} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders all tag labels", () => {
    const tags = [
      makeTag({ id: "a", label: "Alpha" }),
      makeTag({ id: "b", label: "Beta" }),
    ];
    render(<SelectedTags tags={tags} onRemove={vi.fn()} />);
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });

  it("renders container with data-testid=selected-tags", () => {
    render(<SelectedTags tags={[makeTag()]} onRemove={vi.fn()} />);
    expect(screen.getByTestId("selected-tags")).toBeInTheDocument();
  });

  it("calls onRemove with tag id when X button clicked", async () => {
    const user = userEvent.setup();
    const onRemove = vi.fn();
    const tags = [makeTag({ id: "removable" })];
    render(<SelectedTags tags={tags} onRemove={onRemove} />);

    await user.click(screen.getByLabelText("Remove Test Tag"));
    expect(onRemove).toHaveBeenCalledWith("removable");
  });

  it("renders icon when provided", () => {
    const tags = [makeTag({ icon: <span data-testid="custom-icon">★</span> })];
    render(<SelectedTags tags={tags} onRemove={vi.fn()} />);
    expect(screen.getByTestId("custom-icon")).toBeInTheDocument();
  });

  it("does not render icon slot when no icon provided", () => {
    const tags = [makeTag()];
    const { container } = render(
      <SelectedTags tags={tags} onRemove={vi.fn()} />,
    );
    const tagSpan = container.querySelector(
      '[class*="inline-flex"][class*="rounded-full"]',
    );
    // The icon wrapper is a span with "flex size-3.5 items-center justify-center" (no "rounded-full")
    // The button also has size-3.5 but has "rounded-full". Check no non-button child has icon classes.
    const children = Array.from(tagSpan?.children ?? []);
    const hasIconWrapper = children.some(
      (el) =>
        el.tagName === "SPAN" &&
        el.className.includes("size-3.5") &&
        !el.className.includes("rounded-full"),
    );
    expect(hasIconWrapper).toBe(false);
  });

  it("applies primary color styling classes", () => {
    render(<SelectedTags tags={[makeTag()]} onRemove={vi.fn()} />);
    const container = screen.getByTestId("selected-tags");
    const tag = container.querySelector(
      '[class*="inline-flex"][class*="rounded-full"]',
    )!;
    expect(tag.className).toContain("text-primary");
    expect(tag.className).toContain("bg-primary/10");
  });

  it("applies custom className", () => {
    render(
      <SelectedTags
        tags={[makeTag()]}
        onRemove={vi.fn()}
        className="my-class"
      />,
    );
    expect(screen.getByTestId("selected-tags")).toHaveClass("my-class");
  });
});

// ── InlineSelectedTag ────────────────────────────────────────────────────────

describe("InlineSelectedTag", () => {
  it("renders tag label text", () => {
    render(
      <InlineSelectedTag
        tag={makeTag({ label: "Inline Label" })}
        onRemove={vi.fn()}
      />,
    );
    expect(screen.getByText("Inline Label")).toBeInTheDocument();
  });

  it("has data-testid=inline-selected-tag", () => {
    render(<InlineSelectedTag tag={makeTag()} onRemove={vi.fn()} />);
    expect(screen.getByTestId("inline-selected-tag")).toBeInTheDocument();
  });

  it("calls onRemove with tag id when X button clicked", async () => {
    const user = userEvent.setup();
    const onRemove = vi.fn();
    render(
      <InlineSelectedTag
        tag={makeTag({ id: "remove-me" })}
        onRemove={onRemove}
      />,
    );

    await user.click(screen.getByLabelText("Remove Test Tag"));
    expect(onRemove).toHaveBeenCalledWith("remove-me");
  });

  it("X button click does not propagate to parent", () => {
    const onParentClick = vi.fn();
    const onRemove = vi.fn();
    render(
      <div onClick={onParentClick}>
        <InlineSelectedTag tag={makeTag()} onRemove={onRemove} />
      </div>,
    );

    const removeBtn = screen.getByLabelText("Remove Test Tag");
    fireEvent.click(removeBtn);

    expect(onRemove).toHaveBeenCalled();
    expect(onParentClick).not.toHaveBeenCalled();
  });

  it("has contentEditable=false", () => {
    render(<InlineSelectedTag tag={makeTag()} onRemove={vi.fn()} />);
    expect(screen.getByTestId("inline-selected-tag")).toHaveAttribute(
      "contenteditable",
      "false",
    );
  });

  it("renders icon when provided", () => {
    render(
      <InlineSelectedTag
        tag={makeTag({ icon: <span data-testid="tag-icon">◆</span> })}
        onRemove={vi.fn()}
      />,
    );
    expect(screen.getByTestId("tag-icon")).toBeInTheDocument();
  });

  it("does not render icon slot when no icon provided", () => {
    const { container } = render(
      <InlineSelectedTag tag={makeTag()} onRemove={vi.fn()} />,
    );
    const wrapper = screen.getByTestId("inline-selected-tag");
    const children = Array.from(wrapper.children);
    // Icon wrapper is a span with "size-3" (not "size-3.5" like the button)
    const hasIconWrapper = children.some(
      (el) =>
        el.tagName === "SPAN" &&
        el.className.includes("size-3") &&
        !el.className.includes("size-3.5"),
    );
    expect(hasIconWrapper).toBe(false);
  });

  it("applies primary color styling classes", () => {
    render(<InlineSelectedTag tag={makeTag()} onRemove={vi.fn()} />);
    const el = screen.getByTestId("inline-selected-tag");
    expect(el.className).toContain("text-primary");
    expect(el.className).toContain("bg-primary/15");
  });

  it("applies cursor-default and select-none classes", () => {
    render(<InlineSelectedTag tag={makeTag()} onRemove={vi.fn()} />);
    const el = screen.getByTestId("inline-selected-tag");
    expect(el.className).toContain("cursor-default");
    expect(el.className).toContain("select-none");
  });

  it("remove button has correct aria-label", () => {
    render(
      <InlineSelectedTag
        tag={makeTag({ label: "My Tag" })}
        onRemove={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Remove My Tag")).toBeInTheDocument();
  });
});
