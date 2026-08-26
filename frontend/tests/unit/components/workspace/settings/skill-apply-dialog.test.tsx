import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

let mockSelectOnValueChange: ((value: string) => void) | null = null;

vi.mock("@/core/i18n/hooks", () => ({
  useI18n: () => ({
    t: {
      settings: {
        skills: {
          applyDialogTitle: "Apply for {name}",
          applyDialogDescription: "Submit your application for this skill",
          applyDialogCurrentVisibility: "Current visibility: {visibility}",
          applyDialogTargetVisibility: "Target Visibility",
          applyDialogVisibilityPrivate: "Private",
          applyDialogVisibilityDepartment: "Department",
          applyDialogVisibilityPublic: "Public",
          applyDialogReason: "Reason",
          applyDialogReasonPlaceholder: "Enter your reason",
          applyDialogCancel: "Cancel",
          applyDialogSubmit: "Submit",
          applyDialogUpgradeHint: "Upgrade requires admin approval",
          applyDialogDowngradeHint: "Downgrade takes effect immediately",
          visibilityUpdated: "Visibility updated",
          applyDialogDowngradeConfirmTitle: "Confirm downgrade",
          applyDialogDowngradeConfirmDescription:
            "Downgrade takes effect immediately. Continue?",
          applyDialogConfirm: "Confirm",
        },
      },
    },
  }),
}));

vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children, open, onOpenChange }: any) =>
    open ? (
      <div data-testid="dialog">
        <div
          data-testid="dialog-overlay"
          onClick={() => onOpenChange?.(false)}
        />
        <div data-testid="dialog-content">{children}</div>
      </div>
    ) : null,
  DialogContent: ({ children }: any) => (
    <div data-testid="dialog-content-inner">{children}</div>
  ),
  DialogHeader: ({ children }: any) => <div>{children}</div>,
  DialogTitle: ({ children }: any) => (
    <div data-testid="dialog-title">{children}</div>
  ),
  DialogDescription: ({ children }: any) => <div>{children}</div>,
  DialogFooter: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("@/components/ui/select", () => ({
  Select: ({ children, onValueChange, value }: any) => {
    mockSelectOnValueChange = onValueChange;
    return (
      <div data-testid="select" data-value={value}>
        {children}
      </div>
    );
  },
  SelectTrigger: ({ children, id }: any) => <div id={id}>{children}</div>,
  SelectValue: ({ placeholder }: any) => (
    <span data-testid="select-value">{placeholder}</span>
  ),
  SelectContent: ({ children }: any) => <div>{children}</div>,
  SelectItem: ({ children, value }: any) => (
    <button
      data-testid={`select-item-${value}`}
      onClick={() => mockSelectOnValueChange?.(value)}
    >
      {children}
    </button>
  ),
}));

vi.mock("@/components/ui/textarea", () => ({
  Textarea: ({ id, value, onChange, placeholder }: any) => (
    <textarea
      id={id}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      data-testid="textarea"
    />
  ),
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, disabled, variant }: any) => (
    <button
      onClick={onClick}
      disabled={disabled}
      data-variant={variant}
      data-testid={`button-${String(children).toLowerCase()}`}
    >
      {children}
    </button>
  ),
}));

vi.mock("@/components/ui/label", () => ({
  Label: ({ children, htmlFor }: any) => (
    <label htmlFor={htmlFor}>{children}</label>
  ),
}));

const mockSkill = {
  id: "1",
  name: "Test Skill",
  description: "A test skill",
  category: "public",
  license: "mit",
  enabled: false,
  visibility: "private",
};

const mockOnOpenChange = vi.fn();
const mockOnSubmit = vi.fn();
const mockOnChange = vi.fn();

let SkillApplyDialog: typeof import("@/components/workspace/settings/skill-apply-dialog").SkillApplyDialog;

beforeEach(async () => {
  vi.clearAllMocks();
  mockSelectOnValueChange = null;
  const mod =
    await import("@/components/workspace/settings/skill-apply-dialog");
  SkillApplyDialog = mod.SkillApplyDialog;
});

afterEach(() => {
  cleanup();
});

describe("SkillApplyDialog", () => {
  test("renders nothing when skill is null", () => {
    render(
      <SkillApplyDialog
        skill={null}
        open={true}
        onOpenChange={mockOnOpenChange}
        onSubmit={mockOnSubmit}
        onChange={mockOnChange}
      />,
    );
    expect(screen.queryByTestId("dialog")).not.toBeInTheDocument();
  });

  test("renders dialog with skill name when open", () => {
    render(
      <SkillApplyDialog
        skill={mockSkill}
        open={true}
        onOpenChange={mockOnOpenChange}
        onSubmit={mockOnSubmit}
        onChange={mockOnChange}
      />,
    );
    expect(screen.getByText("Apply for Test Skill")).toBeInTheDocument();
  });

  test("does not show dialog when open is false", () => {
    render(
      <SkillApplyDialog
        skill={mockSkill}
        open={false}
        onOpenChange={mockOnOpenChange}
        onSubmit={mockOnSubmit}
        onChange={mockOnChange}
      />,
    );
    expect(screen.queryByTestId("dialog")).not.toBeInTheDocument();
  });

  test("defaults target visibility to current visibility", () => {
    render(
      <SkillApplyDialog
        skill={mockSkill}
        open={true}
        onOpenChange={mockOnOpenChange}
        onSubmit={mockOnSubmit}
        onChange={mockOnChange}
      />,
    );
    expect(screen.getByTestId("select")).toHaveAttribute(
      "data-value",
      "private",
    );
  });

  test("disables submit when target equals current visibility", () => {
    render(
      <SkillApplyDialog
        skill={mockSkill}
        open={true}
        onOpenChange={mockOnOpenChange}
        onSubmit={mockOnSubmit}
        onChange={mockOnChange}
      />,
    );
    expect(screen.getByTestId("button-submit")).toBeDisabled();
  });

  test("shows upgrade hint and calls onSubmit with correct args when upgraded", async () => {
    const user = userEvent.setup();
    render(
      <SkillApplyDialog
        skill={mockSkill}
        open={true}
        onOpenChange={mockOnOpenChange}
        onSubmit={mockOnSubmit}
        onChange={mockOnChange}
      />,
    );

    await user.click(screen.getByTestId("select-item-public"));
    expect(
      screen.getByText("Upgrade requires admin approval"),
    ).toBeInTheDocument();

    const textarea = screen.getByTestId("textarea");
    await user.type(textarea, "I need this skill");

    await user.click(screen.getByTestId("button-submit"));

    expect(mockOnSubmit).toHaveBeenCalledWith("public", "I need this skill");
    expect(mockOnChange).not.toHaveBeenCalled();
  });

  test("shows downgrade hint, hides reason, and confirms before changing", async () => {
    const user = userEvent.setup();
    render(
      <SkillApplyDialog
        skill={{ ...mockSkill, visibility: "public" }}
        open={true}
        onOpenChange={mockOnOpenChange}
        onSubmit={mockOnSubmit}
        onChange={mockOnChange}
      />,
    );

    await user.click(screen.getByTestId("select-item-private"));
    expect(
      screen.getByText("Downgrade takes effect immediately"),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("textarea")).not.toBeInTheDocument();

    await user.click(screen.getByTestId("button-submit"));

    expect(screen.getByText("Confirm downgrade")).toBeInTheDocument();
    expect(mockOnChange).not.toHaveBeenCalled();

    await user.click(screen.getByTestId("button-confirm"));

    expect(mockOnChange).toHaveBeenCalledWith("private", false);
    expect(mockOnSubmit).not.toHaveBeenCalled();
    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });

  test("cancels downgrade confirmation without applying the change", async () => {
    const user = userEvent.setup();
    render(
      <SkillApplyDialog
        skill={{ ...mockSkill, visibility: "public" }}
        open={true}
        onOpenChange={mockOnOpenChange}
        onSubmit={mockOnSubmit}
        onChange={mockOnChange}
      />,
    );

    await user.click(screen.getByTestId("select-item-private"));
    await user.click(screen.getByTestId("button-submit"));
    await user.click(screen.getByTestId("button-cancel"));

    expect(mockOnChange).not.toHaveBeenCalled();
    expect(screen.getByText("Apply for Test Skill")).toBeInTheDocument();
  });

  test("calls onOpenChange(false) on cancel", async () => {
    const user = userEvent.setup();
    render(
      <SkillApplyDialog
        skill={mockSkill}
        open={true}
        onOpenChange={mockOnOpenChange}
        onSubmit={mockOnSubmit}
        onChange={mockOnChange}
      />,
    );

    await user.click(screen.getByTestId("button-cancel"));

    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });

  test("resets form after submission", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <SkillApplyDialog
        skill={mockSkill}
        open={true}
        onOpenChange={mockOnOpenChange}
        onSubmit={mockOnSubmit}
        onChange={mockOnChange}
      />,
    );

    await user.click(screen.getByTestId("select-item-public"));
    const textarea = screen.getByTestId("textarea");
    await user.type(textarea, "I need this skill");

    await user.click(screen.getByTestId("button-submit"));

    expect(mockOnSubmit).toHaveBeenCalledWith("public", "I need this skill");
    expect(mockOnOpenChange).toHaveBeenCalledWith(false);

    rerender(
      <SkillApplyDialog
        skill={mockSkill}
        open={true}
        onOpenChange={mockOnOpenChange}
        onSubmit={mockOnSubmit}
        onChange={mockOnChange}
      />,
    );

    expect(screen.getByTestId("select")).toHaveAttribute(
      "data-value",
      "private",
    );
    expect(screen.getByTestId("textarea")).toHaveValue("");
  });

  test("calls onOpenChange(false) when dialog overlay is clicked", async () => {
    const user = userEvent.setup();
    render(
      <SkillApplyDialog
        skill={mockSkill}
        open={true}
        onOpenChange={mockOnOpenChange}
        onSubmit={mockOnSubmit}
        onChange={mockOnChange}
      />,
    );

    await user.click(screen.getByTestId("dialog-overlay"));
    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });

  test("disables submit button while submitting", async () => {
    const user = userEvent.setup();

    let resolveSubmit!: (value: void) => void;
    const submitPromise = new Promise<void>((resolve) => {
      resolveSubmit = resolve;
    });
    const asyncOnSubmit = vi.fn().mockReturnValue(submitPromise);

    render(
      <SkillApplyDialog
        skill={mockSkill}
        open={true}
        onOpenChange={mockOnOpenChange}
        onSubmit={asyncOnSubmit}
        onChange={mockOnChange}
      />,
    );

    await user.click(screen.getByTestId("select-item-public"));
    await user.type(screen.getByTestId("textarea"), "need this");
    await user.click(screen.getByTestId("button-submit"));

    expect(screen.getByTestId("button-submit")).toBeDisabled();

    resolveSubmit(undefined);
    await vi.waitFor(() => {
      expect(screen.getByTestId("select")).toHaveAttribute(
        "data-value",
        "private",
      );
      expect(screen.getByTestId("textarea")).toHaveValue("");
    });
  });

  test("submits with empty reason", async () => {
    const user = userEvent.setup();
    render(
      <SkillApplyDialog
        skill={mockSkill}
        open={true}
        onOpenChange={mockOnOpenChange}
        onSubmit={mockOnSubmit}
        onChange={mockOnChange}
      />,
    );

    await user.click(screen.getByTestId("select-item-department"));
    await user.click(screen.getByTestId("button-submit"));

    expect(mockOnSubmit).toHaveBeenCalledWith("department", "");
  });

  test("does not call onOpenChange after unmount during async submission", async () => {
    const user = userEvent.setup();
    let resolveSubmit!: (value: void) => void;
    const submitPromise = new Promise<void>((resolve) => {
      resolveSubmit = resolve;
    });
    const asyncOnSubmit = vi.fn().mockReturnValue(submitPromise);

    const { unmount } = render(
      <SkillApplyDialog
        skill={mockSkill}
        open={true}
        onOpenChange={mockOnOpenChange}
        onSubmit={asyncOnSubmit}
        onChange={mockOnChange}
      />,
    );

    await user.click(screen.getByTestId("select-item-public"));
    await user.type(screen.getByTestId("textarea"), "need this");

    await user.click(screen.getByTestId("button-submit"));

    unmount();

    resolveSubmit(undefined);

    await vi.waitFor(() => {
      expect(mockOnOpenChange).not.toHaveBeenCalled();
    });
  });
});
