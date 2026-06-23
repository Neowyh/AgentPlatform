import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
  DialogClose,
  DialogOverlay,
  DialogPortal,
} from "@/components/ui/dialog";

afterEach(() => {
  cleanup();
});

describe("Dialog", () => {
  test("renders with open content", () => {
    render(
      <Dialog open>
        <DialogContent data-testid="dialog-content">
          <DialogTitle>My Dialog</DialogTitle>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByTestId("dialog-content")).toBeInTheDocument();
  });

  test("applies data-slot attribute on Dialog", () => {
    render(
      <Dialog open>
        <DialogOverlay data-testid="dialog-overlay" />
      </Dialog>,
    );
    expect(screen.getByTestId("dialog-overlay")).toBeInTheDocument();
  });
});

describe("DialogTrigger", () => {
  test("renders a trigger button", () => {
    render(
      <Dialog>
        <DialogTrigger data-testid="dialog-trigger">Open</DialogTrigger>
      </Dialog>,
    );
    expect(screen.getByTestId("dialog-trigger")).toBeInTheDocument();
    expect(screen.getByText("Open")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Dialog>
        <DialogTrigger data-testid="dt-slot">Open</DialogTrigger>
      </Dialog>,
    );
    expect(screen.getByTestId("dt-slot")).toHaveAttribute(
      "data-slot",
      "dialog-trigger",
    );
  });
});

describe("DialogContent", () => {
  test("renders content when open", () => {
    render(
      <Dialog open>
        <DialogContent data-testid="dc">Content</DialogContent>
      </Dialog>,
    );
    expect(screen.getByTestId("dc")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Dialog open>
        <DialogContent data-testid="dc-slot">Content</DialogContent>
      </Dialog>,
    );
    expect(screen.getByTestId("dc-slot")).toHaveAttribute(
      "data-slot",
      "dialog-content",
    );
  });

  test("renders close button by default", () => {
    render(
      <Dialog open>
        <DialogContent>Content</DialogContent>
      </Dialog>,
    );
    expect(screen.getByText("Close")).toBeInTheDocument();
  });

  test("hides close button when showCloseButton is false", () => {
    render(
      <Dialog open>
        <DialogContent showCloseButton={false}>Content</DialogContent>
      </Dialog>,
    );
    expect(screen.queryByText("Close")).not.toBeInTheDocument();
  });
});

describe("DialogHeader", () => {
  test("renders with children", () => {
    render(
      <Dialog open>
        <DialogContent>
          <DialogHeader data-testid="dh">Header</DialogHeader>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByTestId("dh")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Dialog open>
        <DialogContent>
          <DialogHeader data-testid="dh-slot">H</DialogHeader>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByTestId("dh-slot")).toHaveAttribute(
      "data-slot",
      "dialog-header",
    );
  });
});

describe("DialogFooter", () => {
  test("renders with children", () => {
    render(
      <Dialog open>
        <DialogContent>
          <DialogFooter data-testid="df">Footer</DialogFooter>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByTestId("df")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Dialog open>
        <DialogContent>
          <DialogFooter data-testid="df-slot">F</DialogFooter>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByTestId("df-slot")).toHaveAttribute(
      "data-slot",
      "dialog-footer",
    );
  });
});

describe("DialogTitle", () => {
  test("renders with text content", () => {
    render(
      <Dialog open>
        <DialogContent>
          <DialogTitle>Dialog Title</DialogTitle>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByText("Dialog Title")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Dialog open>
        <DialogContent>
          <DialogTitle data-testid="dt-title-slot">T</DialogTitle>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByTestId("dt-title-slot")).toHaveAttribute(
      "data-slot",
      "dialog-title",
    );
  });
});

describe("DialogDescription", () => {
  test("renders with text content", () => {
    render(
      <Dialog open>
        <DialogContent>
          <DialogDescription>Desc text</DialogDescription>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByText("Desc text")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Dialog open>
        <DialogContent>
          <DialogDescription data-testid="dd-slot">D</DialogDescription>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByTestId("dd-slot")).toHaveAttribute(
      "data-slot",
      "dialog-description",
    );
  });
});

describe("DialogClose", () => {
  test("renders a close button", () => {
    render(
      <Dialog open>
        <DialogContent>
          <DialogClose data-testid="dc-close">X</DialogClose>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByTestId("dc-close")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Dialog open>
        <DialogContent>
          <DialogClose data-testid="dc-close-slot">X</DialogClose>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByTestId("dc-close-slot")).toHaveAttribute(
      "data-slot",
      "dialog-close",
    );
  });
});
