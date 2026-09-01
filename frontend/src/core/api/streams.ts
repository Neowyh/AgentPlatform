/**
 * Legacy re-export — `streams.ts` is now a thin adapter over `stream-mode.ts`.
 *
 * Keeping this file avoids breaking imports (`@/core/api/streams`) while
 * ensuring one canonical **interface** lives in `stream-mode.ts`.
 */
export * from "./stream-mode";
