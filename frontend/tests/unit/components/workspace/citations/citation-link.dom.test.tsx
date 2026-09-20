import { afterEach, describe, expect, it, rs } from "@rstest/core";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

rs.mock("@/core/api/fetcher", () => ({ fetch: rs.fn() }));

import { CitationLink } from "@/components/workspace/citations/citation-link";
import { fetch } from "@/core/api/fetcher";

afterEach(() => {
  cleanup();
  rs.clearAllMocks();
});

describe("Evidence citation interaction", () => {
  it("opens from the keyboard, reads the matching item, and restores focus", async () => {
    const user = userEvent.setup();
    rs.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({
        receipts: [
          {
            items: [
              {
                evidence_id: "rr_test_i1",
                display_name: "Policies.pdf",
                content: "Keep the policy fragment visible.",
                position: { page: 4 },
                score: 0.91,
              },
            ],
          },
        ],
      }),
    } as Response);

    render(
      <CitationLink href="evidence://rr_test_i1" runId="run-1">
        Policies.pdf — Page 4
      </CitationLink>,
    );

    const trigger = screen.getByRole("button", {
      name: "Open Policies.pdf — Page 4",
    });
    trigger.focus();
    await user.keyboard("{Enter}");

    expect(await screen.findByTestId("evidence-panel")).toBeTruthy();
    expect(
      await screen.findByText("Keep the policy fragment visible."),
    ).toBeTruthy();
    expect(screen.getByText("Retrieval score: 0.91")).toBeTruthy();

    await user.keyboard("{Escape}");
    await waitFor(() => expect(document.activeElement).toBe(trigger));
  });

  it("shows unavailable for an evidence ID absent from the run", async () => {
    const user = userEvent.setup();
    rs.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ receipts: [] }),
    } as Response);

    render(
      <CitationLink href="evidence://rr_missing_i1" runId="run-1">
        Missing evidence
      </CitationLink>,
    );

    await user.click(
      screen.getByRole("button", { name: "Open Missing evidence" }),
    );
    expect(
      await screen.findByText("This knowledge evidence is unavailable."),
    ).toBeTruthy();
  });

  it("shows a generic restricted state without rendering receipt metadata", async () => {
    const user = userEvent.setup();
    rs.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({
        receipts: [{ result_status: "access_restricted", items: [] }],
      }),
    } as Response);

    render(
      <CitationLink href="evidence://rr_private_i1" runId="run-1">
        Restricted evidence
      </CitationLink>,
    );

    await user.click(
      screen.getByRole("button", { name: "Open Restricted evidence" }),
    );
    expect(
      await screen.findByText("This knowledge evidence is restricted."),
    ).toBeTruthy();
  });
});
