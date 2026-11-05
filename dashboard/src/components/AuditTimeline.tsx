import React from 'react';
import { History } from 'lucide-react';
import { AuditLog } from '../types';

interface AuditTimelineProps {
  logs: AuditLog[];
}

export const AuditTimeline: React.FC<AuditTimelineProps> = ({ logs }) => {
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

  return (
    <div className="panel-card p-5 flex flex-col space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <History className="w-5 h-5 text-sky-400" />
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200">
            Immutable Decision & Intervention Audit Trail
          </h2>
        </div>
        <span className="text-xs font-mono text-slate-400">
          CHRONOLOGICAL LOGS
        </span>
      </div>

      <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
        {logs.length === 0 ? (
          <div className="text-center py-6 text-xs text-slate-500 font-mono">
            No audit records registered yet.
          </div>
        ) : (
          logs.map((log) => (
            <div
              key={log.id}
              className="border border-slate-800/80 rounded bg-slate-950/40 p-2.5 flex items-start justify-between font-mono text-xs hover:border-slate-700"
            >
              <div className="flex items-start space-x-3">
                <span className={`badge ${getActionBadgeClass(log.action)} mt-0.5`}>
                  {log.action}
                </span>
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-slate-200 font-semibold">{log.entity_id}</span>
                    <span className="text-slate-500">|</span>
                    <span className="text-slate-400">{log.entity_type}</span>
                    <span className="text-slate-500">by</span>
                    <span className="text-sky-400">{log.actor}</span>
                  </div>
                  {log.details && (
                    <div className="text-[11px] text-slate-500 mt-0.5 line-clamp-1">
                      {JSON.stringify(log.details)}
                    </div>
                  )}
                </div>
              </div>

              <div className="text-[11px] text-slate-500 shrink-0">
                {new Date(log.timestamp * 1000).toLocaleTimeString()}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
