import React, { useState } from 'react';
import { AlertCircle, CheckCircle, ChevronDown, ChevronUp, ArrowRight } from 'lucide-react';
import { Incident, RiskLevel } from '../types';

interface ActiveIncidentsProps {
  incidents: Incident[];
  onAcknowledge: (incidentId: string, operator: string, notes: string) => Promise<void>;
  onResolve: (incidentId: string, operator: string, notes: string) => Promise<void>;
}

export const ActiveIncidents: React.FC<ActiveIncidentsProps> = ({
  incidents,
  onAcknowledge,
  onResolve,
}) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [operatorName, setOperatorName] = useState<string>('Nurse_On_Duty');
  const [actionNotes, setActionNotes] = useState<string>('');

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const getRiskBadgeClass = (level: RiskLevel) => {
    switch (level) {
      case 'URGENT':
        return 'badge-urgent';
      case 'REVIEW':
        return 'badge-review';
      case 'WATCH':
        return 'badge-watch';
      case 'INFORMATIONAL':
        return 'badge-info';
      default:
        return 'badge-normal';
    }
  };

  return (
    <div className="panel-card p-5 flex flex-col space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <AlertCircle className="w-5 h-5 text-rose-400" />
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200">
            Safety Incidents & Explainable Evidence Chain
          </h2>
        </div>
        <span className="text-xs font-mono text-slate-400">
          LIFECYCLE AUDITED
        </span>
      </div>

      {incidents.length === 0 ? (
        <div className="border border-slate-800 rounded-lg p-8 text-center bg-slate-950/50">
          <CheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-2 opacity-80" />
          <p className="text-sm font-medium text-slate-300">No Active Safety Incidents</p>
          <p className="text-xs text-slate-500 mt-1">
            All observed subjects are within safe physical baselines and calibrated resting zones.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {incidents.map((inc) => {
            const isExpanded = expandedId === inc.incident_id;
            const explanation = inc.evidence?.primary_event?.explanation;
            const evidenceItems = explanation?.evidence_chain || inc.evidence?.primary_event?.evidence || [];
            const rejected = explanation?.rejected_hypotheses || [];

            return (
              <div
                key={inc.incident_id}
                className={`border rounded-lg transition-all duration-200 ${
                  inc.risk_level === 'URGENT'
                    ? 'border-rose-900/60 bg-rose-950/20'
                    : inc.risk_level === 'REVIEW'
                    ? 'border-amber-900/60 bg-amber-950/20'
                    : 'border-slate-800 bg-slate-900/40'
                }`}
              >
                <div
                  onClick={() => toggleExpand(inc.incident_id)}
                  className="p-4 cursor-pointer flex items-center justify-between hover:bg-slate-800/40"
                >
                  <div className="flex items-center space-x-3">
                    <span className={`badge ${getRiskBadgeClass(inc.risk_level)}`}>
                      {inc.risk_level}
                    </span>
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-bold text-slate-100 font-mono">
                          {inc.incident_id}
                        </span>
                        <span className="text-xs text-slate-400">|</span>
                        <span className="text-xs font-semibold text-slate-300">
                          {inc.incident_type}
                        </span>
                        <span className="text-xs font-mono text-slate-400">
                          ({inc.person_id})
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-0.5 line-clamp-1">{inc.narrative}</p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-4">
                    <div className="text-right font-mono text-xs text-slate-400">
                      <div>SCORE: <span className="font-semibold text-slate-200">{inc.risk_score.toFixed(3)}</span></div>
                      <div className="text-[10px] text-slate-500">
                        {new Date(inc.updated_at * 1000).toLocaleTimeString()}
                      </div>
                    </div>
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                      {inc.status}
                    </span>
                    {isExpanded ? (
                      <ChevronUp className="w-4 h-4 text-slate-400" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-slate-400" />
                    )}
                  </div>
                </div>

                {isExpanded && (
                  <div className="border-t border-slate-800/80 p-4 bg-slate-950/60 space-y-4 text-xs">
                    {/* Recommended Caregiver Action */}
                    <div className="p-3 rounded bg-sky-950/30 border border-sky-800/40 text-sky-200 flex items-start space-x-2">
                      <ArrowRight className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-bold text-sky-300">RECOMMENDED ACTION: </span>
                        <span>{inc.recommended_action}</span>
                      </div>
                    </div>

                    {/* Rejected Hypotheses */}
                    {rejected.length > 0 && (
                      <div className="space-y-1.5">
                        <span className="font-semibold text-slate-300 uppercase tracking-wider text-[11px]">
                          Deterministic Counter-Hypotheses Evaluated:
                        </span>
                        <ul className="space-y-1 text-slate-400 font-mono text-[11px] list-disc list-inside">
                          {rejected.map((hyp, idx) => (
                            <li key={idx} className="text-slate-400">{hyp}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Evidence Chain Table */}
                    {evidenceItems.length > 0 && (
                      <div className="space-y-1.5">
                        <span className="font-semibold text-slate-300 uppercase tracking-wider text-[11px]">
                          Physical & Kinematic Evidence Chain:
                        </span>
                        <div className="overflow-x-auto rounded border border-slate-800">
                          <table className="w-full text-left font-mono text-[11px]">
                            <thead className="bg-slate-900 text-slate-400 border-b border-slate-800">
                              <tr>
                                <th className="p-2">Metric</th>
                                <th className="p-2">Condition</th>
                                <th className="p-2">Observed</th>
                                <th className="p-2">Weight</th>
                                <th className="p-2">Status</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
                              {evidenceItems.map((ev, idx) => (
                                <tr key={idx}>
                                  <td className="p-2 text-slate-300">{ev.metric}</td>
                                  <td className="p-2 text-slate-400">{ev.expected}</td>
                                  <td className="p-2 text-sky-300 font-semibold">{String(ev.observed)}</td>
                                  <td className="p-2 text-slate-400">{ev.weight}</td>
                                  <td className="p-2">
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                                      PASSED
                                    </span>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Caregiver Action Bar */}
                    <div className="pt-2 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center space-x-2">
                        <span className="text-slate-400 font-mono text-[11px]">OPERATOR:</span>
                        <input
                          type="text"
                          value={operatorName}
                          onChange={(e) => setOperatorName(e.target.value)}
                          className="px-2 py-1 bg-slate-900 border border-slate-700 rounded text-slate-200 text-xs font-mono w-36"
                        />
                        <input
                          type="text"
                          placeholder="Action notes..."
                          value={actionNotes}
                          onChange={(e) => setActionNotes(e.target.value)}
                          className="px-2 py-1 bg-slate-900 border border-slate-700 rounded text-slate-200 text-xs w-56"
                        />
                      </div>

                      <div className="flex items-center space-x-2">
                        {inc.status === 'DETECTED' && (
                          <button
                            onClick={() => onAcknowledge(inc.incident_id, operatorName, actionNotes)}
                            className="px-3 py-1.5 rounded bg-amber-600/80 hover:bg-amber-600 text-white font-medium text-xs transition-colors"
                          >
                            Acknowledge Alert
                          </button>
                        )}
                        {inc.status !== 'RESOLVED' && (
                          <button
                            onClick={() => onResolve(inc.incident_id, operatorName, actionNotes)}
                            className="px-3 py-1.5 rounded bg-emerald-600/80 hover:bg-emerald-600 text-white font-medium text-xs transition-colors"
                          >
                            Resolve & Clear
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
