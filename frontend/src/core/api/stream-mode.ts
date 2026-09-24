/**
 * Stream-mode validation — single source of truth for LangGraph stream modes.
 *
 * This module is the canonical **seam** for stream-mode validation.
 * `streams.ts` re-exports from here so callers have one owner and one
 * **interface** (`sanitizeRunStreamOptions`). Unknown modes now fail closed
 * (throw) instead of being silently dropped — locality: bad config is
 * reported at the call site, not hidden in a once-only console.warn.
 */

export const SUPPORTED_RUN_STREAM_MODES = new Set([
  "values",
  "messages-tuple",
  "updates",
  "debug",
  "tasks",
  "checkpoints",
  "custom",
] as const);

export const CHAT_RUN_STREAM_MODES = [
  "messages-tuple",
  "updates",
  "custom",
] as const;

const warnedUnsupportedStreamModes = new Set<string>();

export function warnUnsupportedStreamModes(
  modes: string[],
  warn: (message: string) => void = console.warn,
) {
  const unseenModes = modes.filter((mode) => {
    if (warnedUnsupportedStreamModes.has(mode)) {
      return false;
    }
    warnedUnsupportedStreamModes.add(mode);
    return true;
  });

  if (unseenModes.length === 0) {
    return;
  }

  warn(
    `[ideer] Dropped unsupported LangGraph stream mode(s): ${unseenModes.join(", ")}`,
  );
}

export function sanitizeRunStreamOptions<T>(options: T): T {
  if (
    typeof options !== "object" ||
    options === null ||
    !("streamMode" in options)
  ) {
    return options;
  }

  const streamMode = (options as { streamMode?: unknown }).streamMode;
  if (streamMode == null) {
    return options;
  }

  const requestedModes = Array.isArray(streamMode) ? streamMode : [streamMode];
  const sanitizedModes = (requestedModes as string[]).filter((mode) =>
    SUPPORTED_RUN_STREAM_MODES.has(mode as never),
  );

  if (sanitizedModes.length === (requestedModes as string[]).length) {
    return options;
  }

  const droppedModes = (requestedModes as string[]).filter(
    (mode) => !SUPPORTED_RUN_STREAM_MODES.has(mode as never),
  );
  warnUnsupportedStreamModes(droppedModes);

  // Fail closed: unknown mode is a caller bug — throw so it surfaces in
  // tests and in the SDK wrapper (`api-client.ts`) rather than being
  // silently ignored. Callers that historically relied on dropping can
  // catch and handle, but new code must fix the mode list.
  throw new Error(
    `[ideer] Unsupported stream mode(s): ${droppedModes.join(", ")} — supported: ${[...SUPPORTED_RUN_STREAM_MODES].join(", ")}`,
  );
}

/** Keep chat streams incremental and avoid retransmitting full thread state. */
export function forceChatRunStreamOptions<T>(options: T): T {
  const requested =
    typeof options === "object" && options !== null
      ? Reflect.get(options, "streamMode")
      : undefined;
  const requestedModes = Array.isArray(requested)
    ? requested
    : requested == null
      ? []
      : [requested];
  // LangGraph's chat client adds these modes by default, but the Gateway's
  // public run contract does not implement them. Chat always includes the
  // equivalent supported messages-tuple stream below.
  const gatewayOptions =
    typeof options === "object" && options !== null
      ? {
          ...options,
          ...(requested == null
            ? {}
            : {
                streamMode: requestedModes.filter(
                  (mode) => mode !== "messages" && mode !== "events",
                ),
              }),
        }
      : options;
  const sanitized = sanitizeRunStreamOptions(gatewayOptions);
  if (typeof sanitized !== "object" || sanitized === null) return sanitized;
  const sanitizedRequested = Reflect.get(sanitized, "streamMode");
  const modes = new Set<string>([
    ...CHAT_RUN_STREAM_MODES,
    ...((Array.isArray(sanitizedRequested)
      ? sanitizedRequested
      : sanitizedRequested == null
        ? []
        : [sanitizedRequested]) as string[]),
  ]);
  modes.delete("values");
  return { ...sanitized, streamMode: [...modes], streamResumable: false } as T;
}
