import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { SettingsSection } from "@/components/workspace/settings/settings-section";

describe("SettingsSection", () => {
  test("renders the title", () => {
    render(
      <SettingsSection title="Profile Settings">
        <div>Content</div>
      </SettingsSection>,
    );
    expect(screen.getByText("Profile Settings")).toBeInTheDocument();
  });

  test("renders children content", () => {
    render(
      <SettingsSection title="Section">
        <div data-testid="child">Child content</div>
      </SettingsSection>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
    expect(screen.getByText("Child content")).toBeInTheDocument();
  });

  test("renders description when provided", () => {
    render(
      <SettingsSection title="Section" description="This is a description">
        <div>Content</div>
      </SettingsSection>,
    );
    expect(screen.getByText("This is a description")).toBeInTheDocument();
  });

  test("does not render description when not provided", () => {
    render(
      <SettingsSection title="Section">
        <div>Content</div>
      </SettingsSection>,
    );
    const descriptions = document.querySelectorAll(".text-muted-foreground");
    // Should not have any description element
    expect(descriptions.length).toBe(0);
  });

  test("renders ReactNode as title", () => {
    render(
      <SettingsSection
        title={<span data-testid="custom-title">Custom Title</span>}
      >
        <div>Content</div>
      </SettingsSection>,
    );
    expect(screen.getByTestId("custom-title")).toBeInTheDocument();
    expect(screen.getByText("Custom Title")).toBeInTheDocument();
  });

  test("renders ReactNode as description", () => {
    render(
      <SettingsSection
        title="Section"
        description={<em data-testid="custom-desc">Italic desc</em>}
      >
        <div>Content</div>
      </SettingsSection>,
    );
    expect(screen.getByTestId("custom-desc")).toBeInTheDocument();
    expect(screen.getByText("Italic desc")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <SettingsSection title="Section" className="my-custom">
        <div>Content</div>
      </SettingsSection>,
    );
    const section = document.querySelector("section.my-custom");
    expect(section).toBeInTheDocument();
  });

  test("renders multiple children", () => {
    render(
      <SettingsSection title="Section">
        <div data-testid="child1">First</div>
        <div data-testid="child2">Second</div>
        <div data-testid="child3">Third</div>
      </SettingsSection>,
    );
    expect(screen.getByTestId("child1")).toBeInTheDocument();
    expect(screen.getByTestId("child2")).toBeInTheDocument();
    expect(screen.getByTestId("child3")).toBeInTheDocument();
  });

  test("has correct semantic structure", () => {
    render(
      <SettingsSection title="Section Title" description="Description text">
        <div>Content</div>
      </SettingsSection>,
    );
    const section = document.querySelector("section");
    expect(section).toBeInTheDocument();
    const header = section?.querySelector("header");
    expect(header).toBeInTheDocument();
    const main = section?.querySelector("main");
    expect(main).toBeInTheDocument();
  });
});
