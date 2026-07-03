export interface VisibilityApplication {
  id: string;
  resource_type: string;
  resource_id: string;
  applicant_id: string;
  current_visibility: string;
  target_visibility: string;
  department_id: string | null;
  reason: string;
  status: string;
  submitted_at: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_comment: string | null;
  version: number;
}

export interface ApplicationsResponse {
  applications: VisibilityApplication[];
  total: number;
  page: number;
  page_size: number;
}
