import { notFound } from "next/navigation";

import { ResourceGallery } from "@/components/workspace/resources/resource-gallery";

const TABS = ["experts", "skills", "connectors"] as const;

export default async function CapabilityTabPage({
  params,
}: {
  params: Promise<{ tab: string }>;
}) {
  const { tab } = await params;
  if (!TABS.includes(tab as (typeof TABS)[number])) notFound();
  return <ResourceGallery defaultTab={tab as (typeof TABS)[number]} />;
}
