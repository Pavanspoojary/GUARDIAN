import React, { useState } from 'react';
import { Sliders, ToggleLeft, ToggleRight, Clock, MapPin, Search } from 'lucide-react';
import { SafetyRule, RiskLevel, Zone } from '../types';

interface PolicyManagerProps {
  rules: SafetyRule[];
  zones?: Zone[];
  onToggleRule: (ruleId: string) => Promise<void>;
}

export const PolicyManager: React.FC<PolicyManagerProps> = ({ rules, zones: _zones = [], onToggleRule }) => {
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [levelFilter, setLevelFilter] = useState<string>('ALL');

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

  const filteredRules = rules.filter((r) => {
    if (levelFilter !== 'ALL' && r.risk_level !== levelFilter) {
      return false;
    }
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      return (
        r.name.toLowerCase().includes(term) ||
        r.description.toLowerCase().includes(term) ||
        r.id.toLowerCase().includes(term)
      );
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* 1. Policy Engine Configuration Panel */}
      <div className="panel-card p-6 flex flex-col space-y-5 bg-[#0f172a] border border-slate-800 rounded-xl shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
              <Sliders className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-100 font-mono">
                Safety Policies & Detection Rules ({rules.length} Configured)
              </h2>
              <p className="text-xs text-slate-400">Priority-ordered deterministic rules evaluated on every frame</p>
            </div>
          </div>

          {/* Search & Level Filter */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search policies..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded-lg pl-8 pr-3 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500 font-mono w-44"
              />
            </div>

            <div className="flex items-center space-x-1 bg-slate-900 border border-slate-800 p-1 rounded-lg">
              {['ALL', 'URGENT', 'REVIEW', 'WATCH'].map((lvl) => (
                <button
                  key={lvl}
                  onClick={() => setLevelFilter(lvl)}
                  className={`px-2.5 py-1 rounded text-[11px] font-mono font-medium transition-colors ${
                    levelFilter === lvl
                      ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {lvl}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Policies Table */}
        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-left font-mono text-xs">
            <thead className="bg-[#090d16] text-slate-400 border-b border-slate-800">
              <tr>
                <th className="p-3">Priority</th>
                <th className="p-3">Policy & Purpose</th>
                <th className="p-3">Risk Level</th>
                <th className="p-3">Base Score</th>
                <th className="p-3">Cooldown</th>
                <th className="p-3">Suppresses</th>
                <th className="p-3 text-right">State</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-[#0c1220]/60">
              {filteredRules.map((r) => (
                <tr key={r.id} className="hover:bg-slate-900/60 transition-colors">
                  <td className="p-3 font-bold text-sky-400">#{r.priority}</td>
                  <td className="p-3">
                    <div className="font-semibold text-slate-200">{r.name}</div>
                    <div className="text-[11px] text-slate-400 mt-0.5">{r.description}</div>
                  </td>
                  <td className="p-3">
                    <span className={`badge ${getRiskBadgeClass(r.risk_level)}`}>
                      {r.risk_level}
                    </span>
                  </td>
                  <td className="p-3 text-slate-200 font-semibold">{r.base_risk_score.toFixed(2)}</td>
                  <td className="p-3 text-slate-400">
                    <div className="flex items-center space-x-1">
                      <Clock className="w-3.5 h-3.5 text-slate-500" />
                      <span>{r.cooldown_seconds}s</span>
                    </div>
                  </td>
                  <td className="p-3 text-[11px]">
                    {r.suppresses.length > 0 ? (
                      <span className="px-1.5 py-0.5 rounded bg-slate-900 text-slate-300 border border-slate-800">
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
                      title={r.enabled ? 'Click to mute policy' : 'Click to activate policy'}
                    >
                      {r.enabled ? (
                        <span className="flex items-center text-emerald-400 text-xs font-semibold bg-emerald-500/10 px-2 py-1 rounded border border-emerald-500/30">
                          <ToggleRight className="w-4 h-4 mr-1 text-emerald-400" />
                          ACTIVE
                        </span>
                      ) : (
                        <span className="flex items-center text-slate-500 text-xs font-semibold bg-slate-800/40 px-2 py-1 rounded border border-slate-700/50">
                          <ToggleLeft className="w-4 h-4 mr-1" />
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

      {/* 2. Configured Safety Zones Panel */}
      <div className="panel-card p-6 bg-[#0f172a] border border-slate-800 rounded-xl shadow-xl space-y-4">
        <div className="flex items-center space-x-3 border-b border-slate-800/80 pb-3">
          <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
            <MapPin className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-100 font-mono">
              Calibrated Room Zones & Spatial Context
            </h3>
            <p className="text-xs text-slate-400">Geofenced safety boundaries used for context-aware risk evaluation</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-lg bg-[#090d16] border border-sky-500/30 font-mono">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-sky-400 uppercase">BED_ZONE</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/30">RESTING</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Designated intentional rest area. Lying down inside this zone suppresses fall alarms and marks posture as intentional sleep.
            </p>
          </div>

          <div className="p-4 rounded-lg bg-[#090d16] border border-emerald-500/30 font-mono">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-emerald-400 uppercase">SAFE_LIVING_AREA</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">MONITORED</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Standard activity zone. Monitored for normal walking, sitting, transitions, and sudden descent events.
            </p>
          </div>

          <div className="p-4 rounded-lg bg-[#090d16] border border-rose-500/30 font-mono">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-rose-400 uppercase">RESTRICTED_STAIRS</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-300 border border-rose-500/30">RESTRICTED</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              High-hazard zone. Entering this perimeter triggers review alerts and activates nighttime wandering rules.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
