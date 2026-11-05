import React from 'react';
import { Sliders, ToggleLeft, ToggleRight, Clock } from 'lucide-react';
import { SafetyRule, RiskLevel } from '../types';

interface PolicyManagerProps {
  rules: SafetyRule[];
  onToggleRule: (ruleId: string) => Promise<void>;
}

export const PolicyManager: React.FC<PolicyManagerProps> = ({ rules, onToggleRule }) => {
  const getRiskBadgeClass = (level: RiskLevel) => {
    switch (level) {
      case 'URGENT':
        return 'badge-urgent';
      case 'REVIEW':
        return 'badge-review';
      case 'WATCH':
        return 'badge-watch';
      default:
        return 'badge-info';
    }
  };

  return (
    <div className="panel-card p-5 flex flex-col space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Sliders className="w-5 h-5 text-sky-400" />
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200">
            Deterministic Policy Engine Configuration ({rules.length} Policies)
          </h2>
        </div>
        <span className="text-xs font-mono text-slate-400">
          PRIORITY ORDERED
        </span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-800">
        <table className="w-full text-left font-mono text-xs">
          <thead className="bg-slate-900 text-slate-400 border-b border-slate-800">
            <tr>
              <th className="p-3">Priority</th>
              <th className="p-3">Policy Name</th>
              <th className="p-3">Risk Level</th>
              <th className="p-3">Base Score</th>
              <th className="p-3">Cooldown</th>
              <th className="p-3">Suppresses</th>
              <th className="p-3 text-right">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
            {rules.map((r) => (
              <tr key={r.id} className="hover:bg-slate-900/40">
                <td className="p-3 font-bold text-sky-400">#{r.priority}</td>
                <td className="p-3">
                  <div className="font-semibold text-slate-200">{r.name}</div>
                  <div className="text-[11px] text-slate-500 line-clamp-1">{r.description}</div>
                </td>
                <td className="p-3">
                  <span className={`badge ${getRiskBadgeClass(r.risk_level)}`}>
                    {r.risk_level}
                  </span>
                </td>
                <td className="p-3 text-slate-300 font-semibold">{r.base_risk_score.toFixed(2)}</td>
                <td className="p-3 text-slate-400 flex items-center space-x-1">
                  <Clock className="w-3 h-3 text-slate-500" />
                  <span>{r.cooldown_seconds}s</span>
                </td>
                <td className="p-3 text-[11px] text-slate-400">
                  {r.suppresses.length > 0 ? (
                    <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                      {r.suppresses.join(', ')}
                    </span>
                  ) : (
                    <span className="text-slate-600">—</span>
                  )}
                </td>
                <td className="p-3 text-right">
                  <button
                    onClick={() => onToggleRule(r.id)}
                    className="inline-flex items-center space-x-1.5 focus:outline-none"
                    title={r.enabled ? 'Click to disable' : 'Click to enable'}
                  >
                    {r.enabled ? (
                      <span className="flex items-center text-emerald-400 text-xs font-semibold">
                        <ToggleRight className="w-5 h-5 mr-1" />
                        ACTIVE
                      </span>
                    ) : (
                      <span className="flex items-center text-slate-500 text-xs font-semibold">
                        <ToggleLeft className="w-5 h-5 mr-1" />
                        MUTED
                      </span>
                    )}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
