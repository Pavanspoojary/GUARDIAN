import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { LiveMonitor } from './components/LiveMonitor';
import { ActiveIncidents } from './components/ActiveIncidents';
import { PolicyManager } from './components/PolicyManager';
import { AuditTimeline } from './components/AuditTimeline';
import { Incident, SafetyRule, Zone, AuditLog } from './types';

export const App: React.FC = () => {
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
      console.error('Error fetching data from SENTINEL API:', err);
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
            // Update active incidents list without overwriting full incident records
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

  // Trigger Scenario
  const handleTriggerScenario = async (scenario: string) => {
    let payload: any = {
      person_id: 'person_01',
      activity: 'STANDING',
      torso_angle: 5.0,
      relative_body_height: 0.95,
      vertical_velocity: 0.0,
      vertical_acceleration: 0.0,
      movement_velocity: 0.0,
      motion_intensity: 0.03,
      floor_proximity: 0.9,
      zone_name: null,
      confidence: 0.96,
    };

    if (scenario === 'bed') {
      payload = {
        ...payload,
        activity: 'LYING',
        torso_angle: 85.0,
        relative_body_height: 0.25,
        vertical_velocity: 0.05,
        floor_proximity: 0.4,
        zone_name: 'BED',
      };
    } else if (scenario === 'fall') {
      payload = {
        ...payload,
        activity: 'LYING_ON_FLOOR',
        torso_angle: 88.0,
        relative_body_height: 0.15,
        vertical_velocity: 1.45,
        floor_proximity: 0.02,
        zone_name: 'FLOOR',
        motion_intensity: 0.01,
      };
    } else if (scenario === 'failed_stand') {
      payload = {
        ...payload,
        activity: 'SITTING',
        torso_angle: 25.0,
        relative_body_height: 0.55,
        movement_velocity: 0.05,
      };
    } else if (scenario === 'wandering') {
      payload = {
        ...payload,
        activity: 'WALKING',
        torso_angle: 10.0,
        relative_body_height: 0.92,
        movement_velocity: 0.35,
        zone_name: 'RESTRICTED',
      };
    }

    try {
      await fetch('/api/simulate-observation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      await fetchData();
    } catch (err) {
      console.error('Failed to trigger simulation scenario:', err);
    }
  };

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
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Header
        wsConnected={wsConnected}
        cameraStatus={cameraStatus}
        activeIncidentsCount={activeIncidents.length}
        onRefresh={fetchData}
      />

      <main className="flex-1 p-6 space-y-6 max-w-7xl mx-auto w-full">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Main Visualizer & Live Monitor */}
          <div className="lg:col-span-7">
            <LiveMonitor
              zones={zones}
              onIncidentTriggered={fetchData}
              onTriggerScenario={handleTriggerScenario}
            />
          </div>

          {/* Active Incidents & Explainable Evidence */}
          <div className="lg:col-span-5">
            <ActiveIncidents
              incidents={incidents}
              onAcknowledge={handleAcknowledge}
              onResolve={handleResolve}
            />
          </div>
        </div>

        {/* Deterministic Policy Engine Configuration */}
        <PolicyManager rules={rules} onToggleRule={handleToggleRule} />

        {/* Audit Trail */}
        <AuditTimeline logs={auditLogs} />
      </main>

      <footer className="border-t border-slate-900 bg-slate-950 py-4 px-6 text-center text-xs text-slate-500 font-mono">
        SENTINEL &copy; 2026 &mdash; Deterministic Human Behaviour & Safety Decision Engine. Offline-First &bull; Zero LLMs &bull; Explainable Safety Verification.
      </footer>
    </div>
  );
};

export default App;
