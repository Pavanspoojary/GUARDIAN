export type RiskLevel = 'NORMAL' | 'INFORMATIONAL' | 'WATCH' | 'REVIEW' | 'URGENT';
export type IncidentStatus = 'DETECTED' | 'UNDER_REVIEW' | 'ACKNOWLEDGED' | 'RESOLVED';

export interface EvidenceItem {
  metric: string;
  expected: string;
  observed: any;
  satisfied: boolean;
  weight: number;
  description: string;
}

export interface Explanation {
  summary: string;
  evidence_chain: EvidenceItem[];
  rejected_hypotheses: string[];
  recommended_action: string;
}

export interface Incident {
  incident_id: string;
  person_id: string;
  incident_type: string;
  risk_level: RiskLevel;
  risk_score: number;
  status: IncidentStatus;
  started_at: number;
  updated_at: number;
  narrative: string;
  recommended_action: string;
  acknowledged_by?: string;
  acknowledged_at?: number;
  resolved_at?: number;
  resolution_notes?: string;
  evidence?: {
    primary_event?: {
      explanation?: Explanation;
      evidence?: EvidenceItem[];
    };
  };
}

export interface TrackedPersonData {
  person_id: string;
  activity: string;
  duration_seconds: number;
  motionless_duration: number;
  failed_attempts: number;
}

export interface SafetyRule {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  priority: number;
  risk_level: RiskLevel;
  base_risk_score: number;
  cooldown_seconds: number;
  suppresses: string[];
  depends_on: string[];
  recommended_action: string;
}

export interface Zone {
  name: string;
  zone_type: string;
  bounds: [number, number, number, number];
  description?: string;
}

export interface AuditLog {
  id: number;
  entity_type: string;
  entity_id: string;
  action: string;
  actor: string;
  timestamp: number;
  details: any;
}
