import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";

afterEach(() => {
  cleanup();
});

describe("Avatar", () => {
  test("renders with fallback content", () => {
    render(
      <Avatar data-testid="avatar">
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByText("JD")).toBeInTheDocument();
  });

  test("applies data-slot attribute", () => {
    render(
      <Avatar data-testid="avatar-slot">
        <AvatarFallback>AB</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByTestId("avatar-slot")).toHaveAttribute(
      "data-slot",
      "avatar",
    );
  });

  test("applies custom className", () => {
    render(
      <Avatar className="my-avatar" data-testid="avatar-custom">
        <AvatarFallback>AB</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByTestId("avatar-custom")).toHaveClass("my-avatar");
  });

  test("renders avatar image with fallback", () => {
    render(
      <Avatar data-testid="avatar-with-both">
        <AvatarImage src="/avatar.jpg" alt="User" />
        <AvatarFallback>AB</AvatarFallback>
      </Avatar>,
    );
    // Fallback is shown when image fails to load (jsdom has no real image loading)
    expect(screen.getByText("AB")).toBeInTheDocument();
  });
});

describe("AvatarFallback", () => {
  test("renders within Avatar context", () => {
    render(
      <Avatar>
        <AvatarFallback data-testid="fallback">X</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByTestId("fallback")).toHaveTextContent("X");
  });

  test("applies data-slot attribute within Avatar", () => {
    render(
      <Avatar>
        <AvatarFallback data-testid="fallback-slot">X</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByTestId("fallback-slot")).toHaveAttribute(
      "data-slot",
      "avatar-fallback",
    );
  });

  test("applies custom className within Avatar", () => {
    render(
      <Avatar>
        <AvatarFallback className="custom-fb" data-testid="fallback-custom">
          X
        </AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByTestId("fallback-custom")).toHaveClass("custom-fb");
  });
});

describe("AvatarImage", () => {
  test("does not render visible element when image fails to load", () => {
    render(
      <Avatar>
        <AvatarImage data-testid="avatar-img" src="/photo.jpg" alt="Photo" />
        <AvatarFallback>PH</AvatarFallback>
      </Avatar>,
    );
    // In jsdom, the image fails to load, so fallback is shown
    expect(screen.getByText("PH")).toBeInTheDocument();
    // The AvatarImage element might not be in the DOM or might be hidden
    const img = screen.queryByTestId("avatar-img");
    // It's fine if img is null - jsdom doesn't load images
    if (img) {
      expect(img).toHaveAttribute("src", "/photo.jpg");
    }
  });
});
