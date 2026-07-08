import { render, screen } from "@testing-library/react";
import { AlertCircle } from "lucide-react";
import { describe, expect, it } from "vitest";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

describe("Alert accessibility", () => {
  it("has role=alert", () => {
    render(
      <Alert>
        <AlertTitle>Heads up!</AlertTitle>
      </Alert>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("contains accessible text content", () => {
    render(
      <Alert>
        <AlertTitle>Error occurred</AlertTitle>
      </Alert>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Error occurred");
  });

  it("has title text accessible to screen readers", () => {
    render(
      <Alert>
        <AlertTitle>Success</AlertTitle>
        <AlertDescription>Operation completed successfully.</AlertDescription>
      </Alert>,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Success");
    expect(alert).toHaveTextContent("Operation completed successfully.");
  });

  it("description is associated with alert", () => {
    render(
      <Alert>
        <AlertTitle>Warning</AlertTitle>
        <AlertDescription>Your session will expire soon.</AlertDescription>
      </Alert>,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Warning");
    expect(alert).toHaveTextContent("Your session will expire soon.");
  });

  it("icon-only alert still has role=alert", () => {
    render(
      <Alert>
        <AlertCircle />
        <AlertTitle>Alert with icon</AlertTitle>
      </Alert>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("destructive variant has alert role", () => {
    render(
      <Alert variant="destructive">
        <AlertTitle>Danger</AlertTitle>
        <AlertDescription>This action cannot be undone.</AlertDescription>
      </Alert>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
