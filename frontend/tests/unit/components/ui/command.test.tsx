import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("cmdk", () => {
  const React = require("react");
  const Input = React.forwardRef((props: any, ref: any) =>
    React.createElement("input", {
      ...props,
      ref,
      "data-slot": props["data-slot"],
    }),
  );
  const List = React.forwardRef((props: any, ref: any) =>
    React.createElement("div", {
      ...props,
      ref,
      "data-slot": props["data-slot"],
    }),
  );
  const Empty = React.forwardRef((props: any, ref: any) =>
    React.createElement("div", {
      ...props,
      ref,
      "data-slot": props["data-slot"],
    }),
  );
  const Group = React.forwardRef((props: any, ref: any) =>
    React.createElement("div", {
      ...props,
      ref,
      "data-slot": props["data-slot"],
    }),
  );
  const Separator = React.forwardRef((props: any, ref: any) =>
    React.createElement("div", {
      ...props,
      ref,
      "data-slot": props["data-slot"],
    }),
  );
  const Item = React.forwardRef((props: any, ref: any) =>
    React.createElement("div", {
      ...props,
      ref,
      "data-slot": props["data-slot"],
    }),
  );
  // The real cmdk exports Command as both a component and a namespace with sub-components
  const Command = React.forwardRef((props: any, ref: any) =>
    React.createElement("div", { ...props, ref, "data-slot": "command" }),
  );
  Command.Input = Input;
  Command.List = List;
  Command.Empty = Empty;
  Command.Group = Group;
  Command.Separator = Separator;
  Command.Item = Item;
  return {
    Command,
    CommandPrimitive: Command,
  };
});

vi.mock("lucide-react", () => ({
  SearchIcon: (props: any) => <svg data-testid="search-icon" />,
}));

vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children, ...props }: any) => (
    <div data-testid="dialog">{children}</div>
  ),
  DialogContent: ({ children, ...props }: any) => (
    <div data-testid="dialog-content">{children}</div>
  ),
  DialogDescription: ({ children }: any) => <span>{children}</span>,
  DialogTitle: ({ children }: any) => <span>{children}</span>,
}));

import {
  Command,
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandShortcut,
  CommandSeparator,
} from "@/components/ui/command";

afterEach(() => {
  cleanup();
});

describe("Command", () => {
  test("renders with data-slot", () => {
    render(
      <Command data-testid="cmd">
        <span>content</span>
      </Command>,
    );
    expect(screen.getByTestId("cmd")).toBeInTheDocument();
  });
});

describe("CommandInput", () => {
  test("renders input with search icon", () => {
    render(<CommandInput data-testid="cmd-input" />);
    expect(screen.getByTestId("cmd-input")).toBeInTheDocument();
    expect(screen.getByTestId("search-icon")).toBeInTheDocument();
  });
});

describe("CommandList", () => {
  test("renders list", () => {
    render(
      <CommandList data-testid="cmd-list">
        <span>items</span>
      </CommandList>,
    );
    expect(screen.getByTestId("cmd-list")).toBeInTheDocument();
  });
});

describe("CommandEmpty", () => {
  test("renders empty state", () => {
    render(<CommandEmpty data-testid="cmd-empty">No results</CommandEmpty>);
    expect(screen.getByText("No results")).toBeInTheDocument();
  });
});

describe("CommandGroup", () => {
  test("renders group", () => {
    render(
      <CommandGroup data-testid="cmd-group">
        <span>group</span>
      </CommandGroup>,
    );
    expect(screen.getByTestId("cmd-group")).toBeInTheDocument();
  });
});

describe("CommandItem", () => {
  test("renders item", () => {
    render(<CommandItem data-testid="cmd-item">Item</CommandItem>);
    expect(screen.getByText("Item")).toBeInTheDocument();
  });
});

describe("CommandShortcut", () => {
  test("renders shortcut", () => {
    render(<CommandShortcut data-testid="shortcut">Ctrl+K</CommandShortcut>);
    expect(screen.getByText("Ctrl+K")).toBeInTheDocument();
  });
});

describe("CommandSeparator", () => {
  test("renders separator", () => {
    render(<CommandSeparator data-testid="separator" />);
    expect(screen.getByTestId("separator")).toBeInTheDocument();
  });
});

describe("CommandDialog", () => {
  test("renders dialog with title", () => {
    render(
      <CommandDialog>
        <CommandItem>Test</CommandItem>
      </CommandDialog>,
    );
    expect(screen.getByTestId("dialog")).toBeInTheDocument();
    expect(screen.getByTestId("dialog-content")).toBeInTheDocument();
  });
});
