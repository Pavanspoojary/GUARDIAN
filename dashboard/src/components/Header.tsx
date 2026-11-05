import React from 'react';
import { Shield, Activity, Radio, RefreshCw, Monitor, AlertTriangle, FileText, Sliders } from 'lucide-react';

export type DashboardTab = 'surveillance' | 'incidents' | 'logs' | 'settings';

interface HeaderProps {
  activeTab: DashboardTab;
  onTabChange: (tab: DashboardTab) => void;
  wsConnected: boolean;
  cameraStatus: string;
  activeIncidentsCount: number;
  onRefresh: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  onTabChange,
  wsConnected,
  cameraStatus,
  activeIncidentsCount,
  onRefresh,
}) => {
  return (
    <header className="border-b border-slate-800 bg-[#090d16]/95 backdrop-blur-md px-6 py-3 flex flex-col md:flex-row md:items-center md:justify-between sticky top-0 z-50 gap-4">
      {/* Brand & Identity */}
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 rounded-lg bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
          <Shield className="w-5 h-5" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-base font-bold text-slate-100 tracking-wider">GUARDIAN</h1>
            <span className="text-[10px] px-1.5 py-0.5 rounded font-mono font-medium bg-slate-800 text-slate-400 border border-slate-700">
              v1.0 DETERMINISTIC
            </span>
          </div>
          <p className="text-[11px] text-slate-400">Human Behaviour & Safety Decision Engine</p>
        </div>
      </div>

      {/* Center: Navigation Tabs */}
      <nav className="flex items-center space-x-1 bg-slate-900/90 border border-slate-800 p-1 rounded-lg">
        <button
          onClick={() => onTabChange('surveillance')}
          className={`flex items-center space-x-2 px-3 py-1.5 rounded-md text-xs font-medium font-mono transition-colors ${
            activeTab === 'surveillance'
              ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
        >
          <Monitor className="w-3.5 h-3.5" />
          <span>SURVEILLANCE HUD</span>
        </button>

        <button
          onClick={() => onTabChange('incidents')}
          className={`flex items-center space-x-2 px-3 py-1.5 rounded-md text-xs font-medium font-mono transition-colors ${
            activeTab === 'incidents'
              ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
        >
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>INCIDENTS</span>
          {activeIncidentsCount > 0 && (
            <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-rose-500 text-white">
              {activeIncidentsCount}
            </span>
          )}
        </button>

        <button
          onClick={() => onTabChange('logs')}
          className={`flex items-center space-x-2 px-3 py-1.5 rounded-md text-xs font-medium font-mono transition-colors ${
            activeTab === 'logs'
              ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>AUDIT LOGS</span>
        </button>

        <button
          onClick={() => onTabChange('settings')}
          className={`flex items-center space-x-2 px-3 py-1.5 rounded-md text-xs font-medium font-mono transition-colors ${
            activeTab === 'settings'
              ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-sm'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
          }`}
        >
          <Sliders className="w-3.5 h-3.5" />
          <span>SAFETY SETTINGS</span>
        </button>
      </nav>

      {/* Right: Telemetry & Status Badges */}
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2 text-xs font-mono">
          <Radio className={`w-3.5 h-3.5 ${wsConnected ? 'text-emerald-400 animate-pulse' : 'text-rose-500'}`} />
          <span className="text-slate-400">WS:</span>
          <span className={wsConnected ? 'text-emerald-400 font-semibold' : 'text-rose-500 font-semibold'}>
            {wsConnected ? 'CONNECTED' : 'DISCONNECTED'}
          </span>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono">
          <Activity className="w-3.5 h-3.5 text-sky-400" />
          <span className="text-slate-400">CAMERA:</span>
          <span className="text-sky-400 font-semibold">{cameraStatus}</span>
        </div>

        {activeIncidentsCount > 0 ? (
          <div className="badge badge-urgent flex items-center space-x-1.5 animate-pulse">
            <span className="w-2 h-2 rounded-full bg-rose-500"></span>
            <span>{activeIncidentsCount} URGENT</span>
          </div>
        ) : (
          <div className="badge badge-normal flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span>ALL SAFE</span>
          </div>
        )}

        <button
          onClick={onRefresh}
          className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors border border-slate-700"
          title="Refresh Data"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
