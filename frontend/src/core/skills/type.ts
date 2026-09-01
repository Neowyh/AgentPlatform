export interface Skill {
  resource_id?: string;
  slug?: string;
  read_only?: boolean;
  name: string;
  description: string;
  summary?: string;
  category: string;
  license: string;
  enabled: boolean;
  visibility?: string | null;
  owner_id?: string | null;
  department_id?: string | null;
  is_favorited?: boolean;
}
