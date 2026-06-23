import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";

import { Image } from "@/components/ai-elements/image";

afterEach(() => {
  cleanup();
});

describe("Image", () => {
  test("renders an img element", () => {
    render(
      <Image
        base64="aGVsbG8="
        uint8Array={new Uint8Array()}
        mediaType="image/png"
        data-testid="ai-image"
      />,
    );
    const img = screen.getByTestId("ai-image");
    expect(img.tagName).toBe("IMG");
  });

  test("sets correct data URI from base64 and mediaType", () => {
    render(
      <Image
        base64="aGVsbG8="
        uint8Array={new Uint8Array()}
        mediaType="image/png"
        data-testid="ai-image"
      />,
    );
    const img = screen.getByTestId("ai-image");
    expect(img).toHaveAttribute("src", "data:image/png;base64,aGVsbG8=");
  });

  test("sets alt text", () => {
    render(
      <Image
        base64="abc"
        uint8Array={new Uint8Array()}
        mediaType="image/jpeg"
        alt="Generated image"
        data-testid="ai-image"
      />,
    );
    expect(screen.getByAltText("Generated image")).toBeInTheDocument();
  });

  test("applies custom className", () => {
    render(
      <Image
        base64="abc"
        uint8Array={new Uint8Array()}
        mediaType="image/png"
        className="custom-image"
        data-testid="ai-image"
      />,
    );
    expect(screen.getByTestId("ai-image")).toHaveClass("custom-image");
  });

  test("has default styling classes", () => {
    render(
      <Image
        base64="abc"
        uint8Array={new Uint8Array()}
        mediaType="image/png"
        data-testid="ai-image"
      />,
    );
    const img = screen.getByTestId("ai-image");
    expect(img.className).toContain("rounded-md");
    expect(img.className).toContain("max-w-full");
  });

  test("handles different media types", () => {
    render(
      <Image
        base64="abc123"
        uint8Array={new Uint8Array()}
        mediaType="image/svg+xml"
        data-testid="ai-image"
      />,
    );
    expect(screen.getByTestId("ai-image")).toHaveAttribute(
      "src",
      "data:image/svg+xml;base64,abc123",
    );
  });

  test("spreads additional img props", () => {
    render(
      <Image
        base64="abc"
        uint8Array={new Uint8Array()}
        mediaType="image/png"
        {...({
          width: 200,
          height: 150,
          "data-testid": "ai-image",
        } as React.ImgHTMLAttributes<HTMLImageElement>)}
      />,
    );
    const img = screen.getByTestId("ai-image");
    expect(img).toHaveAttribute("width", "200");
    expect(img).toHaveAttribute("height", "150");
  });
});
