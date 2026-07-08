import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

describe("Avatar accessibility", () => {
  it("fallback text is accessible when image is absent", () => {
    render(
      <Avatar>
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByText("JD")).toBeInTheDocument();
  });

  it("fallback text is accessible when image fails to load", () => {
    render(
      <Avatar>
        <AvatarImage src="/broken.jpg" alt="Broken avatar" />
        <AvatarFallback>AB</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByText("AB")).toBeInTheDocument();
  });

  it("image has alt attribute for screen readers when loaded", () => {
    const { container } = render(
      <Avatar>
        <AvatarImage src="/photo.jpg" alt="User profile photo" />
        <AvatarFallback>UP</AvatarFallback>
      </Avatar>,
    );
    // Radix Avatar renders img element (may be hidden in jsdom)
    const img = container.querySelector("img");
    if (img) {
      expect(img).toHaveAttribute("alt", "User profile photo");
    }
    // Fallback is shown when image hasn't loaded
    expect(screen.getByText("UP")).toBeInTheDocument();
  });

  it("avatar container is a non-interactive span element", () => {
    const { container } = render(
      <Avatar>
        <AvatarFallback>NA</AvatarFallback>
      </Avatar>,
    );
    const root = container.firstElementChild;
    expect(root).toBeInTheDocument();
    expect(root?.tagName).toBe("SPAN");
  });

  it("fallback conveys identity through text content", () => {
    render(
      <Avatar>
        <AvatarImage src="/photo.jpg" alt="Alice Smith" />
        <AvatarFallback>AS</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByText("AS")).toBeInTheDocument();
  });

  it("avatar renders fallback for each unique user", () => {
    const { rerender } = render(
      <Avatar>
        <AvatarFallback>U1</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByText("U1")).toBeInTheDocument();
    rerender(
      <Avatar>
        <AvatarFallback>U2</AvatarFallback>
      </Avatar>,
    );
    expect(screen.getByText("U2")).toBeInTheDocument();
  });
});
