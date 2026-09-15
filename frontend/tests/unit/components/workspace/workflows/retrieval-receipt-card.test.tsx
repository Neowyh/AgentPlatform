import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { RetrievalReceiptCard } from "@/components/workspace/workflows/retrieval-receipt-card";

describe("RetrievalReceiptCard", () => {
  test("renders loading and error states without pretending evidence is empty", () => {
    const { rerender } = render(<RetrievalReceiptCard loading />);
    expect(screen.getByText("Loading retrieval evidence…")).toBeInTheDocument();

    rerender(<RetrievalReceiptCard error="Evidence unavailable" />);
    expect(screen.getByText("Evidence unavailable")).toBeInTheDocument();
    expect(screen.queryByText("No matching content.")).not.toBeInTheDocument();
  });

  test("renders bounded receipt content as text", () => {
    render(
      <RetrievalReceiptCard
        snapshot={{
          run_evidence: {
            retrieval_receipts: [
              {
                receipt_id: "rr-1",
                knowledge_base_id: "kb-12345678",
                revision_no: 2,
                result_status: "success",
                items: [
                  {
                    display_name: "Policy.pdf",
                    content: "<script>not executable</script>",
                    position: { page: 4 },
                  },
                ],
              },
            ],
          },
        }}
      />,
    );

    expect(screen.getByTestId("retrieval-receipts")).toBeInTheDocument();
    expect(
      screen.getByText("<script>not executable</script>"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Page 4/)).toBeInTheDocument();
  });

  test("renders an empty result without fabricating an item", () => {
    render(
      <RetrievalReceiptCard
        snapshot={{
          run_evidence: {
            retrieval_receipts: [
              { receipt_id: "rr-1", result_status: "empty_hit", items: [] },
            ],
          },
        }}
      />,
    );

    expect(screen.getByText("No matching content.")).toBeInTheDocument();
    expect(screen.queryByText("Unnamed document")).not.toBeInTheDocument();
  });
});
