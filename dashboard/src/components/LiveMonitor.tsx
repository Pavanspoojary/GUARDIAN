import React, { useRef, useEffect, useState } from 'react';
import { Play, Eye, AlertTriangle, UserCheck, ShieldAlert, Footprints, Moon } from 'lucide-react';
import { Zone, TrackedPersonData } from '../types';

interface LiveMonitorProps {
  zones: Zone[];
  activePeople: TrackedPersonData[];
  onTriggerScenario: (scenario: string) => Promise<void>;
}

export const LiveMonitor: React.FC<LiveMonitorProps> = ({
  zones,
  activePeople,
  onTriggerScenario,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [animTime, setAnimTime] = useState(0);
  const [simulating, setSimulating] = useState(false);
  const [activeScenario, setActiveScenario] = useState<string>('idle');

  // Animation loop for canvas
  useEffect(() => {
    let animId: number;
    const loop = () => {
      setAnimTime((t) => t + 0.03);
      animId = requestAnimationFrame(loop);
    };
    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, []);

  // Draw scene
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Clear background
    ctx.fillStyle = '#0b0f19';
    ctx.fillRect(0, 0, width, height);

    // Grid lines
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;
    for (let x = 0; x < width; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y < height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // Floor line (y = 0.85)
    const floorY = height * 0.85;
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 6]);
    ctx.beginPath();
    ctx.moveTo(0, floorY);
    ctx.lineTo(width, floorY);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = '#f59e0b';
    ctx.font = '10px JetBrains Mono';
    ctx.fillText('CALIBRATED FLOOR PLANE (y = 0.85)', 15, floorY - 6);

    // Draw Zones
    zones.forEach((z) => {
      const [ymin, xmin, ymax, xmax] = z.bounds;
      const zx = xmin * width;
      const zy = ymin * height;
      const zw = (xmax - xmin) * width;
      const zh = (ymax - ymin) * height;

      if (z.zone_type === 'BED') {
        ctx.fillStyle = 'rgba(56, 189, 248, 0.08)';
        ctx.strokeStyle = '#38bdf8';
      } else if (z.zone_type === 'RESTRICTED') {
        ctx.fillStyle = 'rgba(239, 68, 68, 0.1)';
        ctx.strokeStyle = '#ef4444';
      } else {
        ctx.fillStyle = 'rgba(16, 185, 129, 0.08)';
        ctx.strokeStyle = '#10b981';
      }

      ctx.fillRect(zx, zy, zw, zh);
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.strokeRect(zx, zy, zw, zh);
      ctx.setLineDash([]);

      ctx.fillStyle = ctx.strokeStyle;
      ctx.font = '11px JetBrains Mono';
      ctx.fillText(`ZONE: ${z.name} [${z.zone_type}]`, zx + 8, zy + 18);
    });

    // Draw simulated / tracked person
    let px = width * 0.45;
    let py = height * 0.45;
    let torsoDeg = 5;
    let bodyH = height * 0.45;
    let label = 'STANDING';
    let badgeColor = '#10b981';

    if (activeScenario === 'fall') {
      // Recumbent on floor
      px = width * 0.40;
      py = floorY - 30;
      torsoDeg = 88;
      bodyH = 40;
      label = 'LYING_ON_FLOOR';
      badgeColor = '#ef4444';
    } else if (activeScenario === 'bed') {
      // Resting on bed
      px = width * 0.20;
      py = height * 0.35;
      torsoDeg = 85;
      bodyH = 50;
      label = 'LYING (BED)';
      badgeColor = '#38bdf8';
    } else if (activeScenario === 'failed_stand') {
      // Sitting with fatigue
      px = width * 0.50;
      py = height * 0.50;
      torsoDeg = 25;
      bodyH = height * 0.28;
      label = 'SITTING (FAILED ASCENT x2)';
      badgeColor = '#f97316';
    } else if (activeScenario === 'wandering') {
      // Near restricted zone
      px = width * 0.75 + Math.sin(animTime * 1.5) * 15;
      py = height * 0.42;
      torsoDeg = 10;
      bodyH = height * 0.42;
      label = 'WALKING (RESTRICTED PERIMETER)';
      badgeColor = '#eab308';
    } else {
      // Normal standing sway
      px += Math.sin(animTime) * 8;
    }

    // Skeleton joints
    ctx.strokeStyle = badgeColor;
    ctx.lineWidth = 2.5;

    // Head
    const headRadius = 14;
    ctx.beginPath();
    ctx.arc(px, py - bodyH / 2, headRadius, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
    ctx.fill();
    ctx.stroke();

    // Spine & Torso
    ctx.beginPath();
    ctx.moveTo(px, py - bodyH / 2 + headRadius);
    ctx.lineTo(px, py);
    ctx.stroke();

    // Limbs based on posture
    if (torsoDeg > 60) {
      // Lying down
      ctx.beginPath();
      ctx.moveTo(px - 30, py + 10);
      ctx.lineTo(px + 40, py + 10);
      ctx.stroke();
    } else {
      // Upright or sitting
      // Arms
      ctx.beginPath();
      ctx.moveTo(px - 20, py - bodyH / 4);
      ctx.lineTo(px + 20, py - bodyH / 4);
      ctx.stroke();

      // Legs
      ctx.beginPath();
      ctx.moveTo(px, py);
      ctx.lineTo(px - 15, py + bodyH / 2);
      ctx.moveTo(px, py);
      ctx.lineTo(px + 15, py + bodyH / 2);
      ctx.stroke();
    }

    // Bounding box
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
    ctx.lineWidth = 1;
    ctx.strokeRect(px - 35, py - bodyH / 2 - 20, 70, bodyH + 30);

    // Label tag
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(px - 45, py - bodyH / 2 - 42, 160, 20);
    ctx.fillStyle = badgeColor;
    ctx.font = 'bold 10px JetBrains Mono';
    ctx.fillText(`person_01: ${label}`, px - 40, py - bodyH / 2 - 28);
  }, [zones, animTime, activeScenario]);

  const handleScenarioClick = async (scenario: string) => {
    setActiveScenario(scenario);
    setSimulating(true);
    await onTriggerScenario(scenario);
    setSimulating(false);
  };

  return (
    <div className="panel-card p-5 flex flex-col space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Eye className="w-5 h-5 text-sky-400" />
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200">
            Real-Time Visual Perception & Tracking Canvas
          </h2>
        </div>
        <span className="text-xs font-mono text-slate-400">
          640x480 NORMALIZED COORD MATRIX
        </span>
      </div>

      <div className="relative rounded-lg overflow-hidden border border-slate-800 bg-slate-950 flex justify-center">
        <canvas
          ref={canvasRef}
          width={640}
          height={400}
          className="w-full max-w-3xl block"
        />

        {/* Live HUD Overlay */}
        <div className="absolute top-3 left-3 bg-slate-900/90 backdrop-blur border border-slate-800 p-2.5 rounded font-mono text-xs space-y-1">
          <div className="text-slate-400">TRACK_ID: <span className="text-slate-200">person_01</span></div>
          <div className="text-slate-400">ACTIVE_TRACKS: <span className="text-slate-200">{activePeople.length || 1}</span></div>
          <div className="text-slate-400">CALIBRATED_ZONES: <span className="text-sky-400">{zones.length}</span></div>
          <div className="text-slate-400">CURRENT_MODE: <span className="text-emerald-400 font-semibold">{activeScenario.toUpperCase()}</span></div>
        </div>
      </div>

      {/* Interactive Verification Scenarios */}
      <div className="pt-2">
        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
          <Play className="w-3.5 h-3.5 text-sky-400" />
          <span>Deterministic Verification Scenarios (Simulate Kinematics)</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          <button
            disabled={simulating}
            onClick={() => handleScenarioClick('idle')}
            className={`px-3 py-2 text-xs font-medium rounded border transition-colors flex items-center justify-center space-x-1.5 ${
              activeScenario === 'idle'
                ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
                : 'bg-slate-800/80 border-slate-700 text-slate-300 hover:bg-slate-700'
            }`}
          >
            <UserCheck className="w-3.5 h-3.5" />
            <span>Normal Standing</span>
          </button>

          <button
            disabled={simulating}
            onClick={() => handleScenarioClick('bed')}
            className={`px-3 py-2 text-xs font-medium rounded border transition-colors flex items-center justify-center space-x-1.5 ${
              activeScenario === 'bed'
                ? 'bg-sky-500/20 border-sky-500/50 text-sky-300'
                : 'bg-slate-800/80 border-slate-700 text-slate-300 hover:bg-slate-700'
            }`}
          >
            <Moon className="w-3.5 h-3.5" />
            <span>Intentional Bed Rest</span>
          </button>

          <button
            disabled={simulating}
            onClick={() => handleScenarioClick('fall')}
            className={`px-3 py-2 text-xs font-medium rounded border transition-colors flex items-center justify-center space-x-1.5 ${
              activeScenario === 'fall'
                ? 'bg-rose-500/20 border-rose-500/50 text-rose-300'
                : 'bg-rose-950/40 border-rose-800/60 text-rose-300 hover:bg-rose-900/60'
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
            <span>Sudden Fall Sequence</span>
          </button>

          <button
            disabled={simulating}
            onClick={() => handleScenarioClick('failed_stand')}
            className={`px-3 py-2 text-xs font-medium rounded border transition-colors flex items-center justify-center space-x-1.5 ${
              activeScenario === 'failed_stand'
                ? 'bg-amber-500/20 border-amber-500/50 text-amber-300'
                : 'bg-slate-800/80 border-slate-700 text-slate-300 hover:bg-slate-700'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Failed Standing x2</span>
          </button>

          <button
            disabled={simulating}
            onClick={() => handleScenarioClick('wandering')}
            className={`px-3 py-2 text-xs font-medium rounded border transition-colors flex items-center justify-center space-x-1.5 ${
              activeScenario === 'wandering'
                ? 'bg-yellow-500/20 border-yellow-500/50 text-yellow-300'
                : 'bg-slate-800/80 border-slate-700 text-slate-300 hover:bg-slate-700'
            }`}
          >
            <Footprints className="w-3.5 h-3.5" />
            <span>Restricted Zone Breach</span>
          </button>
        </div>
      </div>
    </div>
  );
};
