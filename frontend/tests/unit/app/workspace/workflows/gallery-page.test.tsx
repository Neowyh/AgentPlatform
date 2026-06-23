import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("@/components/workspace/workflows/workflow-gallery", () => ({
  WorkflowGallery: () => (
    <div data-testid="workflow-gallery">Workflow Gallery</div>
  ),
}));

import WorkflowsPage from "@/app/workspace/workflows/page";

afterEach(() => {
  cleanup();
});

describe("WorkflowsPage", () => {
  test("renders WorkflowGallery component", () => {
    render(<WorkflowsPage />);
    expect(screen.getByTestId("workflow-gallery")).toBeInTheDocument();
  });

  test("renders WorkflowGallery with expected text", () => {
    render(<WorkflowsPage />);
    expect(screen.getByText("Workflow Gallery")).toBeInTheDocument();
  });
});
