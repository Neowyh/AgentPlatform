export const VISIBILITY_RANKS: Record<string, number> = {
  private: 0,
  department: 1,
  public: 2,
} as const;

export type VisibilityChange = "upgrade" | "downgrade" | "unchanged";

const PRIVATE_RANK = VISIBILITY_RANKS.private!;

export function classifyVisibilityChange(
  currentVisibility: string | null | undefined,
  targetVisibility: string,
): VisibilityChange {
  const currentRank =
    VISIBILITY_RANKS[currentVisibility ?? "private"] ?? PRIVATE_RANK;
  const targetRank = VISIBILITY_RANKS[targetVisibility];
  if (targetRank === undefined) return "unchanged";
  if (targetRank > currentRank) return "upgrade";
  if (targetRank < currentRank) return "downgrade";
  return "unchanged";
}
