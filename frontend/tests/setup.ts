import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
import "@testing-library/jest-dom/vitest";

// Polyfill IntersectionObserver for jsdom (used by landing page animations)
if (typeof globalThis.IntersectionObserver === "undefined") {
  globalThis.IntersectionObserver = class IntersectionObserver {
    root = null;
    rootMargin = "";
    thresholds = [0];
    constructor(
      _callback: IntersectionObserverCallback,
      _options?: IntersectionObserverInit,
    ) {}
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords(): IntersectionObserverEntry[] {
      return [];
    }
  };
}

// Polyfill pointer capture methods for Radix UI components in jsdom
// jsdom does not implement these, causing "target.hasPointerCapture is not a function"
if (!HTMLElement.prototype.hasPointerCapture) {
  HTMLElement.prototype.hasPointerCapture = function () {
    return false;
  };
}
if (!HTMLElement.prototype.setPointerCapture) {
  HTMLElement.prototype.setPointerCapture = function () {
    // no-op
  };
}

// Polyfill scrollIntoView for Radix UI Select in jsdom
// jsdom does not implement scrollIntoView
if (!HTMLElement.prototype.scrollIntoView) {
  HTMLElement.prototype.scrollIntoView = function () {
    // no-op
  };
}

afterEach(() => {
  cleanup();
});
