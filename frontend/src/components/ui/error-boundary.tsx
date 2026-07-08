import { Component, type ErrorInfo, type ReactNode } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode | ((error: Error, reset: () => void) => ReactNode);
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  resetKeys?: unknown[];
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.props.onError?.(error, errorInfo);
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps): void {
    if (!this.state.hasError) return;

    const prevKeys = prevProps.resetKeys;
    const currKeys = this.props.resetKeys;

    const changed =
      (prevKeys === undefined) !== (currKeys === undefined) ||
      (prevKeys !== undefined &&
        currKeys !== undefined &&
        (prevKeys.length !== currKeys.length ||
          prevKeys.some((key, index) => key !== currKeys[index])));

    if (changed) {
      this.reset();
    }
  }

  reset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback !== undefined) {
        if (typeof this.props.fallback === "function") {
          return this.props.fallback(
            this.state.error ?? new Error("Unknown error"),
            this.reset,
          );
        }
        return this.props.fallback;
      }

      return (
        <Alert variant="destructive" data-testid="error-boundary-fallback">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <AlertTitle>Something went wrong</AlertTitle>
          <AlertDescription>
            An unexpected error occurred. Please try again.
          </AlertDescription>
          <div className="col-start-2 mt-2">
            <Button
              variant="outline"
              size="sm"
              data-testid="error-boundary-retry"
              onClick={this.reset}
            >
              Try Again
            </Button>
          </div>
        </Alert>
      );
    }

    return this.props.children;
  }
}
