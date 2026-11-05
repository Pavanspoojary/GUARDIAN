import React, { useState, useEffect, useCallback } from 'react';
import { Header, DashboardTab } from './components/Header';
import { LiveMonitor } from './components/LiveMonitor';
import { ActiveIncidents } from './components/ActiveIncidents';
import { PolicyManager } from './components/PolicyManager';
import { AuditTimeline } from './components/AuditTimeline';
import { Incident, SafetyRule, Zone, AuditLog } from './types';
import { LayoutGrid, Maximize } from 'lucide-react';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<DashboardTab>('surveillance');
  const [surveillanceMode, setSurveillanceMode] = useState<'fullscreen' | 'split'>('fullscreen');
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [rules, setRules] = useState<SafetyRule[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [cameraStatus, setCameraStatus] = useState<string>('ONLINE');
  const [wsConnected, setWsConnected] = useState<boolean>(false);

  // Fetch initial data from backend (rules & zones are static)
  const fetchData = useCallback(async () => {
    try {
      const [incRes, rulesRes, zonesRes, healthRes] = await Promise.all([
        fetch('/api/incidents'),
        fetch('/api/rules'),
        fetch('/api/zones'),
        fetch('/api/health'),
      ]);

      if (incRes.ok) setIncidents(await incRes.json());
      if (rulesRes.ok) setRules(await rulesRes.json());
      if (zonesRes.ok) setZones(await zonesRes.json());
      if (healthRes.ok) {
        const h = await healthRes.json();
        setCameraStatus(h.camera_status);
      }
    } catch (err) {
      console.error('Error fetching data from GUARDIAN API:', err);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Load audit logs only when viewing logs tab
  useEffect(() => {
    if (activeTab === 'logs') {
      fetch('/api/audit-logs')
        .then((r) => r.ok && r.json())
        .then((logs) => logs && setAuditLogs(logs))
        .catch((err) => console.warn('Audit logs load error:', err));
    }
  }, [activeTab]);

  // WebSocket connection for real-time telemetry (zero polling loops)
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/live`;
    let ws: WebSocket | null = null;
    let reconnectTimeout: any = null;

    const connectWs = () => {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.camera_status) setCameraStatus(data.camera_status);

          // Only sync full incidents when count actually changes (prevents 10 req/s spam)
          if (data.active_incidents && Array.isArray(data.active_incidents)) {
            setIncidents((prev) => {
              const prevActiveCount = prev.filter((i) => i.status !== 'RESOLVED').length;
              if (data.active_incidents.length !== prevActiveCount) {
                fetch('/api/incidents')
                  .then((r) => r.ok && r.json())
                  .then((updated) => updated && setIncidents(updated))
                  .catch((err) => console.warn('Incidents sync error:', err));
              }
              return prev;
            });
          }
        } catch (e) {
          console.error('WebSocket parse error:', e);
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        reconnectTimeout = setTimeout(connectWs, 3000);
      };

      ws.onerror = () => {
        setWsConnected(false);
      };
    };

    connectWs();

    return () => {
      if (ws) ws.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, []);

  // Acknowledge incident
  const handleAcknowledge = async (incidentId: string, operator: string, notes: string) => {
    try {
      const res = await fetch(`/api/incidents/${incidentId}/acknowledge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ operator, notes }),
      });
      if (res.ok) {
        await fetchData();
      }
    } catch (err) {
      console.error('Failed to acknowledge incident:', err);
    }
  };

  // Resolve incident
  const handleResolve = async (incidentId: string, operator: string, notes: string) => {
    try {
      const res = await fetch(`/api/incidents/${incidentId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ operator, notes }),
      });
      if (res.ok) {
        await fetchData();
      }
    } catch (err) {
      console.error('Failed to resolve incident:', err);
    }
  };

  // Toggle rule
  const handleToggleRule = async (ruleId: string) => {
    try {
      const res = await fetch(`/api/rules/${ruleId}/toggle`, { method: 'POST' });
      if (res.ok) {
        await fetchData();
      }
    } catch (err) {
      console.error('Failed to toggle rule:', err);
    }
  };

  const activeIncidents = incidents.filter((i) => i.status !== 'RESOLVED');

  return (
    <div className="min-h-screen bg-[#070a12] text-slate-100 flex flex-col font-sans">
      <Header
        activeTab={activeTab}
        onTabChange={setActiveTab}
        wsConnected={wsConnected}
        cameraStatus={cameraStatus}
        activeIncidentsCount={activeIncidents.length}
        onRefresh={fetchData}
      />

      {/* Main Content Area */}
      <main className={`flex-1 flex flex-col ${activeTab === 'surveillance' ? 'p-3 w-full' : 'p-6 max-w-7xl mx-auto w-full'}`}>
        {/* Tab 1: Live Surveillance HUD */}
        {activeTab === 'surveillance' && (
          <div className="flex-1 flex flex-col space-y-2">
            {/* Top Toolbar for Surveillance Mode */}
            <div className="flex items-center justify-end px-2 text-xs font-mono">
              <div className="flex items-center space-x-1 bg-slate-900 border border-slate-800 p-1 rounded-lg">
                <button
                  onClick={() => setSurveillanceMode('fullscreen')}
                  className={`flex items-center space-x-1.5 px-3 py-1 rounded text-[11px] font-medium transition-colors ${
                    surveillanceMode === 'fullscreen'
                      ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title="Webcam Full Screen View"
                >
                  <Maximize className="w-3 h-3" />
                  <span>FULLSCREEN WEBCAM</span>
                </button>

                <button
                  onClick={() => setSurveillanceMode('split')}
                  className={`flex items-center space-x-1.5 px-3 py-1 rounded text-[11px] font-medium transition-colors ${
                    surveillanceMode === 'split'
                      ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                  title="Side-by-side Camera and Incidents Console"
                >
                  <LayoutGrid className="w-3 h-3" />
                  <span>SPLIT COMMAND VIEW</span>
                </button>
              </div>
            </div>

            {/* Layout Rendering */}
            {surveillanceMode === 'fullscreen' ? (
              <div className="flex-1 w-full">
                <LiveMonitor
                  onIncidentTriggered={fetchData}
                  activeIncidents={incidents}
                  onAcknowledge={handleAcknowledge}
                  onResolve={handleResolve}
                />
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start flex-1">
                <div className="lg:col-span-8">
                  <LiveMonitor
                    onIncidentTriggered={fetchData}
                    activeIncidents={incidents}
                    onAcknowledge={handleAcknowledge}
                    onResolve={handleResolve}
                  />
                </div>
                <div className="lg:col-span-4 space-y-4">
                  <ActiveIncidents
                    incidents={incidents}
                    onAcknowledge={handleAcknowledge}
                    onResolve={handleResolve}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Incidents Management Console */}
        {activeTab === 'incidents' && (
          <div className="space-y-6">
            <ActiveIncidents
              incidents={incidents}
              onAcknowledge={handleAcknowledge}
              onResolve={handleResolve}
            />
          </div>
        )}

        {/* Tab 3: Chronological Audit Logs */}
        {activeTab === 'logs' && (
          <div className="space-y-6">
            <AuditTimeline logs={auditLogs} />
          </div>
        )}

        {/* Tab 4: Safety Settings & Policy Configuration */}
        {activeTab === 'settings' && (
          <div className="space-y-6">
            <PolicyManager
              rules={rules}
              zones={zones}
              onToggleRule={handleToggleRule}
            />
          </div>
        )}
      </main>

      <footer className="border-t border-slate-900 bg-[#06080e] py-3 px-6 text-center text-xs text-slate-500 font-mono flex flex-col sm:flex-row sm:items-center sm:justify-between w-full gap-2">
        <div>
          GUARDIAN &copy; 2026 &mdash; Deterministic Human Behaviour & Safety Decision Engine
        </div>
        <div className="flex items-center space-x-3 text-[11px] text-slate-400">
          <span>OFFLINE LOCAL-FIRST</span>
          <span>&bull;</span>
          <span>ADAPTIVE INFERENCE</span>
          <span>&bull;</span>
          <span>ZERO CLOUD APIS</span>
        </div>
      </footer>
    </div>
  );
};

export default App;
