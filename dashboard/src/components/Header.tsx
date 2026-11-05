import React from 'react';
import { Shield, Activity, Radio, RefreshCw } from 'lucide-react';

interface HeaderProps {
  wsConnected: boolean;
  cameraStatus: string;
  activeIncidentsCount: number;
  onRefresh: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  wsConnected,
  cameraStatus,
  activeIncidentsCount,
  onRefresh,
}) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur px-6 py-4 flex items-center justify-between sticky top-0 z-50">
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 rounded-lg bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
          <Shield className="w-6 h-6" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-lg font-bold text-slate-100 tracking-wider">GUARDIAN</h1>
            <span className="text-xs px-2 py-0.5 rounded font-mono font-medium bg-slate-800 text-slate-400 border border-slate-700">
              v1.0 DETERMINISTIC
            </span>
          </div>
          <p className="text-xs text-slate-400">Human Behaviour & Safety Decision Engine</p>
        </div>
      </div>

      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-2 text-xs font-mono">
          <Radio className={`w-4 h-4 ${wsConnected ? 'text-emerald-400 animate-pulse' : 'text-rose-500'}`} />
          <span className="text-slate-400">TELEMETRY:</span>
          <span className={wsConnected ? 'text-emerald-400 font-semibold' : 'text-rose-500 font-semibold'}>
            {wsConnected ? 'CONNECTED' : 'DISCONNECTED'}
          </span>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono">
          <Activity className="w-4 h-4 text-sky-400" />
          <span className="text-slate-400">CAMERA:</span>
          <span className="text-sky-400 font-semibold">{cameraStatus}</span>
        </div>

        {activeIncidentsCount > 0 ? (
          <div className="badge badge-urgent flex items-center space-x-1.5 animate-pulse">
            <span className="w-2 h-2 rounded-full bg-rose-500"></span>
            <span>{activeIncidentsCount} ACTIVE INCIDENT{activeIncidentsCount > 1 ? 'S' : ''}</span>
          </div>
        ) : (
          <div className="badge badge-normal flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span>ALL MONITORED SAFE</span>
          </div>
        )}

        <button
          onClick={onRefresh}
          className="p-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors border border-slate-700"
          title="Refresh Data"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
