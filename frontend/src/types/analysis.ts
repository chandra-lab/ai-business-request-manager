export interface AIAnalysis {
  id: string;
  provider: string;
  status: string;
  confidence: number | null;
  recommended_department_id: string | null;
  recommended_department_code: string | null;
  rationale: string | null;
  model_id: string | null;
  prompt_version: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  duration_ms: number | null;
  created_at: string;
}
