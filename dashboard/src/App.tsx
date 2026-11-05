import React, { useState, useEffect, useCallback } from 'react';
import { Header, DashboardTab } from './components/Header';
import { LiveMonitor } from './components/LiveMonitor';
import { ActiveIncidents } from './components/ActiveIncidents';
import { PolicyManager } from './components/PolicyManager';
import { AuditTimeline } from './components/AuditTimeline';
import { Incident, SafetyRule, Zone, AuditLog } from './types';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<DashboardTab>('surveillance');
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [rules, setRules] = useState<SafetyRule[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [cameraStatus, setCameraStatus] = useState<string>('ONLINE');
  const [wsConnected, setWsConnected] = useState<boolean>(false);

  // Fetch data from backend
  const fetchData = useCallback(async () => {
    try {
      const [incRes, rulesRes, zonesRes, logsRes, healthRes] = await Promise.all([
        fetch('/api/incidents'),
        fetch('/api/rules'),
        fetch('/api/zones'),
        fetch('/api/audit-logs'),
        fetch('/api/health'),
      ]);

      if (incRes.ok) setIncidents(await incRes.json());
      if (rulesRes.ok) setRules(await rulesRes.json());
      if (zonesRes.ok) setZones(await zonesRes.json());
      if (logsRes.ok) setAuditLogs(await logsRes.json());
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

  // WebSocket connection for real-time telemetry
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
          if (data.active_incidents) {
            fetchData();
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
  }, [fetchData]);

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

      <main className="flex-1 p-6 max-w-7xl mx-auto w-full">
        {/* Tab 1: Live Surveillance HUD */}
        {activeTab === 'surveillance' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Live Camera & HUD Panel */}
            <div className="lg:col-span-7">
              <LiveMonitor onIncidentTriggered={fetchData} />
            </div>

            {/* Live Incident & Alerts Queue */}
            <div className="lg:col-span-5 space-y-6">
              <ActiveIncidents
                incidents={incidents}
                onAcknowledge={handleAcknowledge}
                onResolve={handleResolve}
              />
            </div>
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

      <footer className="border-t border-slate-900 bg-[#06080e] py-4 px-6 text-center text-xs text-slate-500 font-mono flex flex-col sm:flex-row sm:items-center sm:justify-between max-w-7xl mx-auto w-full gap-2">
        <div>
          GUARDIAN &copy; 2026 &mdash; Deterministic Human Behaviour & Safety Decision Engine
        </div>
        <div className="flex items-center space-x-3 text-[11px] text-slate-400">
          <span>OFFLINE LOCAL-FIRST</span>
          <span>&bull;</span>
          <span>ZERO LLMS</span>
          <span>&bull;</span>
          <span>STRICT EXPLAINABILITY</span>
        </div>
      </footer>
    </div>
  );
};

export default App;
