export interface Skill {
  resource_id?: string;
  slug?: string;
  read_only?: boolean;
  name: string;
  description: string;
  description_zh?: string | null;
  summary?: string;
  category: string;
  license: string;
  enabled: boolean;
  visibility?: string | null;
  owner_id?: string | null;
  department_id?: string | null;
  is_favorited?: boolean;
  latest_version?: number;
  draft_revision?: number;
  can_modify?: boolean;
  system_owned?: boolean;
  allowed_tools?: string[] | null;
  requires_internet?: boolean;
  skill_md?: string;
  published_at?: string | null;
}
