import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test } from "vitest";

import {
  Queue,
  QueueItem,
  QueueItemIndicator,
  QueueItemContent,
  QueueItemDescription,
  QueueItemActions,
  QueueItemAction,
  QueueItemAttachment,
  QueueItemImage,
  QueueItemFile,
  QueueList,
  QueueSection,
  QueueSectionTrigger,
  QueueSectionLabel,
  QueueSectionContent,
} from "@/components/ai-elements/queue";

afterEach(() => {
  cleanup();
});

describe("Queue", () => {
  test("renders with children", () => {
    render(
      <Queue data-testid="queue">
        <p>Queue content</p>
      </Queue>,
    );
    expect(screen.getByTestId("queue")).toBeInTheDocument();
    expect(screen.getByText("Queue content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Queue className="custom-queue" data-testid="queue">
        <p>Content</p>
      </Queue>,
    );
    expect(screen.getByTestId("queue")).toHaveClass("custom-queue");
  });

  test("has border and rounded classes", () => {
    render(<Queue data-testid="queue" />);
    const el = screen.getByTestId("queue");
    expect(el.className).toContain("rounded-xl");
    expect(el.className).toContain("border");
    expect(el.className).toContain("flex");
  });
});

describe("QueueItem", () => {
  test("renders as a list item with children", () => {
    render(
      <QueueItem data-testid="item">
        <span>Item content</span>
      </QueueItem>,
    );
    const item = screen.getByTestId("item");
    expect(item.tagName).toBe("LI");
    expect(screen.getByText("Item content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <QueueItem className="custom-item" data-testid="item">
        <span>Content</span>
      </QueueItem>,
    );
    expect(screen.getByTestId("item")).toHaveClass("custom-item");
  });

  test("has hover and transition classes", () => {
    render(
      <QueueItem data-testid="item">
        <span>Content</span>
      </QueueItem>,
    );
    const el = screen.getByTestId("item");
    expect(el.className).toContain("hover:bg-muted");
    expect(el.className).toContain("transition-colors");
  });
});

describe("QueueItemIndicator", () => {
  test("renders default pending state", () => {
    render(<QueueItemIndicator data-testid="indicator" />);
    const el = screen.getByTestId("indicator");
    expect(el.tagName).toBe("SPAN");
    expect(el.className).toContain("rounded-full");
    expect(el.className).toContain("border");
  });

  test("applies completed styling when completed=true", () => {
    render(<QueueItemIndicator completed data-testid="indicator" />);
    const el = screen.getByTestId("indicator");
    expect(el.className).toContain("bg-muted-foreground/10");
  });

  test("applies pending styling when completed=false", () => {
    render(<QueueItemIndicator completed={false} data-testid="indicator" />);
    const el = screen.getByTestId("indicator");
    expect(el.className).toContain("border-muted-foreground/50");
  });

  test("applies custom className", () => {
    render(
      <QueueItemIndicator
        className="custom-indicator"
        data-testid="indicator"
      />,
    );
    expect(screen.getByTestId("indicator")).toHaveClass("custom-indicator");
  });
});

describe("QueueItemContent", () => {
  test("renders with children", () => {
    render(
      <QueueItemContent data-testid="content">Task name</QueueItemContent>,
    );
    expect(screen.getByText("Task name")).toBeInTheDocument();
  });

  test("applies completed styling when completed=true", () => {
    render(
      <QueueItemContent completed data-testid="content">
        Done task
      </QueueItemContent>,
    );
    const el = screen.getByTestId("content");
    expect(el.className).toContain("line-through");
    expect(el.className).toContain("text-muted-foreground/50");
  });

  test("applies pending styling when completed=false", () => {
    render(
      <QueueItemContent completed={false} data-testid="content">
        Pending task
      </QueueItemContent>,
    );
    const el = screen.getByTestId("content");
    expect(el.className).toContain("text-muted-foreground");
    expect(el.className).not.toContain("line-through");
  });

  test("applies custom className", () => {
    render(
      <QueueItemContent className="custom-content" data-testid="content">
        Content
      </QueueItemContent>,
    );
    expect(screen.getByTestId("content")).toHaveClass("custom-content");
  });
});

describe("QueueItemDescription", () => {
  test("renders with children", () => {
    render(
      <QueueItemDescription data-testid="desc">
        Description text
      </QueueItemDescription>,
    );
    expect(screen.getByText("Description text")).toBeInTheDocument();
  });

  test("applies completed styling", () => {
    render(
      <QueueItemDescription completed data-testid="desc">
        Done
      </QueueItemDescription>,
    );
    const el = screen.getByTestId("desc");
    expect(el.className).toContain("line-through");
  });

  test("applies pending styling", () => {
    render(
      <QueueItemDescription completed={false} data-testid="desc">
        Pending
      </QueueItemDescription>,
    );
    const el = screen.getByTestId("desc");
    expect(el.className).toContain("text-muted-foreground");
  });

  test("has ml-6 class for indentation", () => {
    render(
      <QueueItemDescription data-testid="desc">Desc</QueueItemDescription>,
    );
    expect(screen.getByTestId("desc").className).toContain("ml-6");
  });
});

describe("QueueItemActions", () => {
  test("renders with children", () => {
    render(
      <QueueItemActions data-testid="actions">
        <button>Action 1</button>
      </QueueItemActions>,
    );
    expect(screen.getByText("Action 1")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <QueueItemActions className="custom-actions" data-testid="actions" />,
    );
    expect(screen.getByTestId("actions")).toHaveClass("custom-actions");
  });

  test("has flex and gap classes", () => {
    render(<QueueItemActions data-testid="actions" />);
    const el = screen.getByTestId("actions");
    expect(el.className).toContain("flex");
    expect(el.className).toContain("gap-1");
  });
});

describe("QueueItemAction", () => {
  test("renders as a button", () => {
    render(
      <QueueItemAction data-testid="action">
        <span>Do something</span>
      </QueueItemAction>,
    );
    const btn = screen.getByTestId("action");
    expect(btn.tagName).toBe("BUTTON");
  });

  test("has opacity-0 and group-hover classes", () => {
    render(
      <QueueItemAction data-testid="action">
        <span>Action</span>
      </QueueItemAction>,
    );
    const el = screen.getByTestId("action");
    expect(el.className).toContain("opacity-0");
    expect(el.className).toContain("group-hover:opacity-100");
  });

  test("applies custom className", () => {
    render(
      <QueueItemAction className="custom-action" data-testid="action">
        <span>Action</span>
      </QueueItemAction>,
    );
    expect(screen.getByTestId("action")).toHaveClass("custom-action");
  });
});

describe("QueueItemAttachment", () => {
  test("renders with children", () => {
    render(
      <QueueItemAttachment data-testid="attachment">
        <span>File attachment</span>
      </QueueItemAttachment>,
    );
    expect(screen.getByText("File attachment")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <QueueItemAttachment
        className="custom-attachment"
        data-testid="attachment"
      />,
    );
    expect(screen.getByTestId("attachment")).toHaveClass("custom-attachment");
  });

  test("has flex-wrap class", () => {
    render(<QueueItemAttachment data-testid="attachment" />);
    expect(screen.getByTestId("attachment").className).toContain("flex-wrap");
  });
});

describe("QueueItemImage", () => {
  test("renders an img element", () => {
    render(<QueueItemImage src="/test.png" alt="Test" data-testid="image" />);
    const img = screen.getByTestId("image");
    expect(img.tagName).toBe("IMG");
    expect(img).toHaveAttribute("src", "/test.png");
  });

  test("has fixed dimensions", () => {
    render(<QueueItemImage src="/test.png" data-testid="image" />);
    const img = screen.getByTestId("image");
    expect(img).toHaveAttribute("width", "32");
    expect(img).toHaveAttribute("height", "32");
  });

  test("applies custom className", () => {
    render(
      <QueueItemImage
        src="/test.png"
        className="custom-image"
        data-testid="image"
      />,
    );
    expect(screen.getByTestId("image")).toHaveClass("custom-image");
  });
});

describe("QueueItemFile", () => {
  test("renders with children and paperclip icon", () => {
    render(
      <QueueItemFile data-testid="file">
        <span>document.pdf</span>
      </QueueItemFile>,
    );
    expect(screen.getByText("document.pdf")).toBeInTheDocument();
    // PaperclipIcon SVG
    const svg = screen.getByTestId("file").querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <QueueItemFile className="custom-file" data-testid="file">
        <span>File</span>
      </QueueItemFile>,
    );
    expect(screen.getByTestId("file")).toHaveClass("custom-file");
  });

  test("has border and rounded classes", () => {
    render(
      <QueueItemFile data-testid="file">
        <span>File</span>
      </QueueItemFile>,
    );
    const el = screen.getByTestId("file");
    expect(el.className).toContain("border");
    expect(el.className).toContain("rounded");
  });
});

describe("QueueList", () => {
  test("renders with children inside a list", () => {
    render(
      <QueueList data-testid="list">
        <QueueItem>
          <span>Item 1</span>
        </QueueItem>
        <QueueItem>
          <span>Item 2</span>
        </QueueItem>
      </QueueList>,
    );
    expect(screen.getByText("Item 1")).toBeInTheDocument();
    expect(screen.getByText("Item 2")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <QueueList className="custom-list" data-testid="list">
        <QueueItem>
          <span>Item</span>
        </QueueItem>
      </QueueList>,
    );
    expect(screen.getByTestId("list")).toHaveClass("custom-list");
  });
});

describe("QueueSection", () => {
  test("renders with children", () => {
    render(
      <QueueSection data-testid="section">
        <p>Section content</p>
      </QueueSection>,
    );
    expect(screen.getByTestId("section")).toBeInTheDocument();
    expect(screen.getByText("Section content")).toBeInTheDocument();
  });

  test("defaults to open", () => {
    render(
      <QueueSection data-testid="section">
        <QueueSectionTrigger>
          <QueueSectionLabel label="tasks" count={3} />
        </QueueSectionTrigger>
        <QueueSectionContent>
          <p>Visible content</p>
        </QueueSectionContent>
      </QueueSection>,
    );
    expect(screen.getByText("Visible content")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <QueueSection className="custom-section" data-testid="section">
        <p>Content</p>
      </QueueSection>,
    );
    expect(screen.getByTestId("section")).toHaveClass("custom-section");
  });
});

describe("QueueSectionTrigger", () => {
  test("renders with children", () => {
    render(
      <QueueSection>
        <QueueSectionTrigger data-testid="trigger">
          <span>Toggle section</span>
        </QueueSectionTrigger>
      </QueueSection>,
    );
    expect(screen.getByText("Toggle section")).toBeInTheDocument();
  });

  test("renders as a button element", () => {
    render(
      <QueueSection>
        <QueueSectionTrigger data-testid="trigger">
          <span>Section header</span>
        </QueueSectionTrigger>
      </QueueSection>,
    );
    const btn = screen.getByTestId("trigger");
    expect(btn.tagName).toBe("BUTTON");
  });

  test("applies custom className", () => {
    render(
      <QueueSection>
        <QueueSectionTrigger className="custom-trigger" data-testid="trigger">
          <span>Header</span>
        </QueueSectionTrigger>
      </QueueSection>,
    );
    expect(screen.getByTestId("trigger")).toHaveClass("custom-trigger");
  });
});

describe("QueueSectionLabel", () => {
  test("renders label text with count", () => {
    render(<QueueSectionLabel label="tasks" count={5} data-testid="label" />);
    expect(screen.getByText("5 tasks")).toBeInTheDocument();
  });

  test("renders chevron icon", () => {
    render(<QueueSectionLabel label="items" count={2} data-testid="label" />);
    const svg = screen.getByTestId("label").querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  test("renders optional icon", () => {
    render(
      <QueueSectionLabel
        label="tasks"
        count={3}
        icon={<span data-testid="custom-icon">I</span>}
        data-testid="label"
      />,
    );
    expect(screen.getByTestId("custom-icon")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <QueueSectionLabel
        label="items"
        count={1}
        className="custom-label"
        data-testid="label"
      />,
    );
    expect(screen.getByTestId("label")).toHaveClass("custom-label");
  });

  test("handles zero count", () => {
    render(<QueueSectionLabel label="errors" count={0} data-testid="label" />);
    expect(screen.getByText("0 errors")).toBeInTheDocument();
  });
});

describe("QueueSectionContent", () => {
  test("renders children", () => {
    render(
      <QueueSection defaultOpen>
        <QueueSectionTrigger>
          <QueueSectionLabel label="items" count={1} />
        </QueueSectionTrigger>
        <QueueSectionContent data-testid="content">
          <p>Section body</p>
        </QueueSectionContent>
      </QueueSection>,
    );
    expect(screen.getByText("Section body")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <QueueSection defaultOpen>
        <QueueSectionTrigger>
          <QueueSectionLabel label="items" count={1} />
        </QueueSectionTrigger>
        <QueueSectionContent className="custom-content" data-testid="content">
          <p>Content</p>
        </QueueSectionContent>
      </QueueSection>,
    );
    expect(screen.getByTestId("content")).toHaveClass("custom-content");
  });
});

describe("Queue composition", () => {
  test("renders a full queue with sections and items", () => {
    render(
      <Queue data-testid="queue">
        <QueueSection defaultOpen>
          <QueueSectionTrigger data-testid="section-trigger">
            <QueueSectionLabel label="tasks" count={2} />
          </QueueSectionTrigger>
          <QueueSectionContent>
            <QueueList>
              <QueueItem data-testid="item1">
                <QueueItemIndicator completed />
                <QueueItemContent completed>Task 1 completed</QueueItemContent>
              </QueueItem>
              <QueueItem data-testid="item2">
                <QueueItemIndicator />
                <QueueItemContent>Task 2 in progress</QueueItemContent>
              </QueueItem>
            </QueueList>
          </QueueSectionContent>
        </QueueSection>
      </Queue>,
    );

    expect(screen.getByText("2 tasks")).toBeInTheDocument();
    expect(screen.getByText("Task 1 completed")).toBeInTheDocument();
    expect(screen.getByText("Task 2 in progress")).toBeInTheDocument();
  });

  test("renders queue items with attachments", () => {
    render(
      <Queue>
        <QueueList>
          <QueueItem data-testid="item">
            <QueueItemContent>Upload file</QueueItemContent>
            <QueueItemAttachment>
              <QueueItemImage src="/thumb.png" />
              <QueueItemFile>
                <span>report.pdf</span>
              </QueueItemFile>
            </QueueItemAttachment>
          </QueueItem>
        </QueueList>
      </Queue>,
    );

    expect(screen.getByText("Upload file")).toBeInTheDocument();
    expect(screen.getByText("report.pdf")).toBeInTheDocument();
    expect(screen.getByTestId("item").querySelector("img")).toBeInTheDocument();
  });
});
