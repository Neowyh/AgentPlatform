import { describe, test, expect } from "vitest";

import enMeta from "@/content/en/_meta";
import enAppMeta from "@/content/en/application/_meta";
import enHarnessMeta from "@/content/en/harness/_meta";
import enIntroMeta from "@/content/en/introduction/_meta";
import enPostsMeta from "@/content/en/posts/_meta";
import enRefMeta from "@/content/en/reference/_meta";
import enRefModelMeta from "@/content/en/reference/model-providers/_meta";
import enTutorialsMeta from "@/content/en/tutorials/_meta";
import zhMeta from "@/content/zh/_meta";
import zhAppMeta from "@/content/zh/application/_meta";
import zhHarnessMeta from "@/content/zh/harness/_meta";
import zhIntroMeta from "@/content/zh/introduction/_meta";
import zhPostsMeta from "@/content/zh/posts/_meta";
import zhRefMeta from "@/content/zh/reference/_meta";
import zhRefModelMeta from "@/content/zh/reference/model-providers/_meta";
import zhTutorialsMeta from "@/content/zh/tutorials/_meta";

interface MetaEntry {
  title?: string;
  type?: string;
}

const metaFiles: [string, Record<string, MetaEntry>][] = [
  ["en/_meta", enMeta as Record<string, MetaEntry>],
  ["en/application/_meta", enAppMeta as Record<string, MetaEntry>],
  ["en/harness/_meta", enHarnessMeta as Record<string, MetaEntry>],
  ["en/introduction/_meta", enIntroMeta as Record<string, MetaEntry>],
  ["en/posts/_meta", enPostsMeta as Record<string, MetaEntry>],
  ["en/reference/_meta", enRefMeta as Record<string, MetaEntry>],
  [
    "en/reference/model-providers/_meta",
    enRefModelMeta as Record<string, MetaEntry>,
  ],
  ["en/tutorials/_meta", enTutorialsMeta as Record<string, MetaEntry>],
  ["zh/_meta", zhMeta as Record<string, MetaEntry>],
  ["zh/application/_meta", zhAppMeta as Record<string, MetaEntry>],
  ["zh/harness/_meta", zhHarnessMeta as Record<string, MetaEntry>],
  ["zh/introduction/_meta", zhIntroMeta as Record<string, MetaEntry>],
  ["zh/posts/_meta", zhPostsMeta as Record<string, MetaEntry>],
  ["zh/reference/_meta", zhRefMeta as Record<string, MetaEntry>],
  [
    "zh/reference/model-providers/_meta",
    zhRefModelMeta as Record<string, MetaEntry>,
  ],
  ["zh/tutorials/_meta", zhTutorialsMeta as Record<string, MetaEntry>],
];

describe("content _meta files", () => {
  for (const [name, meta] of metaFiles) {
    test(`${name} exports a non-null object`, () => {
      expect(typeof meta).toBe("object");
      expect(meta).not.toBeNull();
    });

    test(`${name} entries have title or type`, () => {
      for (const [key, value] of Object.entries(meta)) {
        expect(typeof key).toBe("string");
        expect(typeof value).toBe("object");
        expect(value).not.toBeNull();
        const hasTitle = typeof value.title === "string";
        const hasType = typeof value.type === "string";
        expect(hasTitle || hasType).toBe(true);
      }
    });
  }

  test("en/_meta has expected section keys", () => {
    const keys = Object.keys(enMeta);
    expect(keys).toContain("index");
    expect(keys).toContain("introduction");
    expect(keys).toContain("harness");
    expect(keys).toContain("application");
    expect(keys).toContain("tutorials");
    expect(keys).toContain("reference");
  });

  test("zh/_meta has expected section keys", () => {
    const keys = Object.keys(zhMeta);
    expect(keys).toContain("index");
    expect(keys).toContain("introduction");
    expect(keys).toContain("harness");
    expect(keys).toContain("application");
    expect(keys).toContain("tutorials");
    expect(keys).toContain("reference");
  });

  test("en/harness/_meta has expected entries", () => {
    expect(enHarnessMeta).toHaveProperty("quick-start");
    expect(enHarnessMeta).toHaveProperty("configuration");
    expect(enHarnessMeta).toHaveProperty("tools");
    expect(enHarnessMeta).toHaveProperty("skills");
  });

  test("en reference model-providers has ark entry", () => {
    expect(enRefModelMeta).toHaveProperty("ark");
    expect((enRefModelMeta as Record<string, MetaEntry>).ark!.title).toBe(
      "火山方舟",
    );
  });

  test("zh reference model-providers has ark entry", () => {
    expect(zhRefModelMeta).toHaveProperty("ark");
    expect((zhRefModelMeta as Record<string, MetaEntry>).ark!.title).toBe(
      "火山方舟",
    );
  });
});
