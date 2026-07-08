import { describe, expect, it } from "vitest";

import type {
  Model,
  ModelsResponse,
  TokenUsageSettings,
} from "@/core/models/types";

describe("Model", () => {
  it("can be constructed with required fields", () => {
    const model: Model = {
      id: "gpt-4",
      name: "GPT-4",
      model: "gpt-4-turbo",
      display_name: "GPT-4 Turbo",
    };
    expect(model.id).toBe("gpt-4");
    expect(model.display_name).toBe("GPT-4 Turbo");
  });

  it("handles optional feature flags", () => {
    const withFeatures: Model = {
      id: "claude-3",
      name: "Claude 3",
      model: "claude-3-opus",
      display_name: "Claude 3 Opus",
      description: "Most capable model",
      supports_thinking: true,
      supports_reasoning_effort: true,
    };
    expect(withFeatures.description).toBe("Most capable model");
    expect(withFeatures.supports_thinking).toBe(true);
    expect(withFeatures.supports_reasoning_effort).toBe(true);
  });

  it("handles null description", () => {
    const model: Model = {
      id: "model-1",
      name: "Model 1",
      model: "model-1",
      display_name: "Model 1",
      description: null,
    };
    expect(model.description).toBeNull();
  });
});

describe("TokenUsageSettings", () => {
  it("can be constructed with enabled flag", () => {
    const settings: TokenUsageSettings = { enabled: true };
    expect(settings.enabled).toBe(true);
  });
});

describe("ModelsResponse", () => {
  it("wraps models array and token settings", () => {
    const response: ModelsResponse = {
      models: [
        {
          id: "gpt-4",
          name: "GPT-4",
          model: "gpt-4",
          display_name: "GPT-4",
        },
      ],
      token_usage: { enabled: false },
    };
    expect(response.models).toHaveLength(1);
    expect(response.token_usage.enabled).toBe(false);
  });
});
