import { redirect } from "next/navigation";

// ADR-0007: the agent surfaces are canonical at /workspace/agents; the
// pre-unification experts paths redirect permanently in both directions.
export default function ExpertsGalleryRedirect() {
  redirect("/workspace/capabilities/agents");
}
