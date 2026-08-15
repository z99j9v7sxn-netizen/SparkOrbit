import type { GeneratedResource } from '../../../api/learnExtras';

export interface ResourceQuality {
  accuracy?: number;
  profile_fit?: number;
  completeness?: number;
  hallucination_risk?: number;
  rationale?: string;
  needs_review?: boolean;
}

export function qualityOf(r: GeneratedResource): ResourceQuality | null {
  const q = (r.meta_json || {}).quality;
  return q && typeof q === 'object' ? (q as ResourceQuality) : null;
}
