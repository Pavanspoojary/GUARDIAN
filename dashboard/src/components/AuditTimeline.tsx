import React, { useState } from 'react';
import { History, Filter, Search } from 'lucide-react';
import { AuditLog } from '../types';

interface AuditTimelineProps {
  logs: AuditLog[];
}

export const AuditTimeline: React.FC<AuditTimelineProps> = ({ logs }) => {
  const [filterType, setFilterType] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');

  const getActionBadgeClass = (action: string) => {
    if (action.includes('DETECTED') || action.includes('ESCALATION')) {
      return 'badge-urgent';
    }
    if (action.includes('ACKNOWLEDGED')) {
      return 'badge-watch';
    }
    if (action.includes('RESOLVED')) {
      return 'badge-normal';
    }
    return 'badge-info';
  };

  const filteredLogs = logs.filter((log) => {
    if (filterType !== 'ALL' && !log.action.includes(filterType)) {
      return false;
    }
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      return (
        log.entity_id.toLowerCase().includes(term) ||
        log.actor.toLowerCase().includes(term) ||
        log.action.toLowerCase().includes(term) ||
        JSON.stringify(log.details || {}).toLowerCase().includes(term)
      );
    }
    return true;
  });

  return (
    <div className="panel-card p-6 flex flex-col space-y-5 bg-[#0f172a] border border-slate-800 rounded-xl shadow-xl">
      {/* Title & Filter Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
            <History className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-100 font-mono">
              Deterministic Safety Audit Trail
            </h2>
            <p className="text-xs text-slate-400">Immutable chronological record of decisions and interventions</p>
          </div>
        </div>

        {/* Filter Buttons & Search */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Filter logs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="bg-slate-900 border border-slate-800 rounded-lg pl-8 pr-3 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500 font-mono w-40"
            />
          </div>

          <div className="flex items-center space-x-1 bg-slate-900 border border-slate-800 p-1 rounded-lg">
            {['ALL', 'DETECTED', 'ACKNOWLEDGED', 'RESOLVED'].map((f) => (
              <button
                key={f}
                onClick={() => setFilterType(f)}
                className={`px-2.5 py-1 rounded text-[11px] font-mono font-medium transition-colors ${
                  filterType === f
                    ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Logs List */}
      <div className="space-y-2.5 max-h-[600px] overflow-y-auto pr-2">
        {filteredLogs.length === 0 ? (
          <div className="text-center py-12 text-xs text-slate-500 font-mono border border-dashed border-slate-800 rounded-lg">
            <Filter className="w-6 h-6 mx-auto mb-2 text-slate-600" />
            No audit records match the selected filters.
          </div>
        ) : (
          filteredLogs.map((log) => (
            <div
              key={log.id}
              className="border border-slate-800/80 rounded-lg bg-[#090d16] p-3 flex flex-col md:flex-row md:items-start justify-between font-mono text-xs hover:border-slate-700 transition-colors gap-2"
            >
              <div className="flex items-start space-x-3">
                <span className={`badge ${getActionBadgeClass(log.action)} mt-0.5 shrink-0`}>
                  {log.action}
                </span>
                <div className="space-y-1">
                  <div className="flex items-center space-x-2 text-slate-200 font-semibold">
                    <span>{log.entity_id}</span>
                    <span className="text-slate-600">&bull;</span>
                    <span className="text-slate-400 font-normal">{log.entity_type}</span>
                    <span className="text-slate-600">&bull;</span>
                    <span className="text-sky-400 text-[11px]">Actor: {log.actor}</span>
                  </div>
                  {log.details && (
                    <div className="text-[11px] text-slate-400 bg-slate-950 p-2 rounded border border-slate-900 font-mono break-all">
                      {typeof log.details === 'object' ? JSON.stringify(log.details) : String(log.details)}
                    </div>
                  )}
                </div>
              </div>

              <div className="text-[11px] text-slate-500 shrink-0 self-start md:self-auto font-mono">
                {new Date(log.timestamp * 1000).toLocaleTimeString()} ({new Date(log.timestamp * 1000).toLocaleDateString()})
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
