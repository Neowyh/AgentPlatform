export interface Skill {
  name: string;
  description: string;
  category: string;
  license: string;
  enabled: boolean;
  visibility?: string | null;
  owner_id?: string | null;
  department_id?: string | null;
}
