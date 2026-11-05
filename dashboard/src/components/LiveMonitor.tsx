import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Camera, Video, Play, Pause, Eye, EyeOff, AlertTriangle } from 'lucide-react';
import { Zone, LiveFrameResult, ActivityDistributionItem } from '../types';

interface LiveMonitorProps {
  zones: Zone[];
  onIncidentTriggered: () => void;
  onTriggerScenario: (scenario: string) => Promise<void>;
}

export const LiveMonitor: React.FC<LiveMonitorProps> = ({
  zones: _zones,
  onIncidentTriggered,
  onTriggerScenario,
}) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Video Source Mode: 'webcam' | 'sample' | 'simulation'
  const [sourceMode, setSourceMode] = useState<'webcam' | 'sample' | 'simulation'>('webcam');
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [showSkeleton, setShowSkeleton] = useState<boolean>(true);
  const [cameraError, setCameraError] = useState<string | null>(null);

  // Telemetry HUD states
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [framesCount, setFramesCount] = useState<number>(0);
  const [latencyMs, setLatencyMs] = useState<number>(45);
  const [narrative, setNarrative] = useState<string>('INITIALIZING DETERMINISTIC SURVEILLANCE PIPELINE...');
  const [distribution, setDistribution] = useState<ActivityDistributionItem[]>([
    { label: 'POSSIBLE FALL · REVIEW', percent: 0.0 },
    { label: 'LYING / RESTING', percent: 0.0 },
    { label: 'SITTING', percent: 0.0 },
    { label: 'STANDING', percent: 92.5 },
    { label: 'WALKING', percent: 5.0 },
    { label: 'UNCLEAR / OTHER', percent: 2.5 },
    { label: 'NO PERSON VISIBLE', percent: 0.0 },
  ]);
  const [activeState, setActiveState] = useState<string>('STANDING');
  const [kinematics, setKinematics] = useState({
    torsoAngle: 5.0,
    relativeHeight: 0.90,
    motionIntensity: 0.02,
    motionlessDuration: 0.0,
  });

  // Start webcam
  const startWebcam = useCallback(async () => {
    setCameraError(null);
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCameraError('Webcam access not supported in this browser environment. Ensure HTTPS or localhost.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
        audio: false,
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.muted = true;
        videoRef.current.onloadedmetadata = () => {
          videoRef.current?.play().catch((e) => console.warn('Webcam autoplay prevented:', e));
        };
        setIsPlaying(true);
      }
    } catch (err: any) {
      console.warn('Webcam permission error:', err);
      setCameraError('Camera access requested. Please allow webcam permission in your browser prompt.');
    }
  }, []);

  // Stop webcam
  const stopWebcam = useCallback(() => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((track) => track.stop());
      videoRef.current.srcObject = null;
    }
  }, []);

  // Switch source mode
  useEffect(() => {
    if (sourceMode === 'webcam') {
      startWebcam();
    } else {
      stopWebcam();
      if (videoRef.current) {
        if (sourceMode === 'sample') {
          videoRef.current.src = '/api/sample-video';
          videoRef.current.loop = true;
          videoRef.current.muted = true;
          videoRef.current.play();
          setIsPlaying(true);
        } else {
          videoRef.current.src = '';
        }
      }
    }
    return () => {
      stopWebcam();
    };
  }, [sourceMode, startWebcam, stopWebcam]);

  // Elapsed timer
  useEffect(() => {
    const timer = setInterval(() => {
      if (isPlaying) {
        setElapsedSeconds((s) => s + 1);
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [isPlaying]);

  // Frame processing loop
  useEffect(() => {
    let timeoutId: any;
    let isProcessing = false;

    const captureAndProcess = async () => {
      if (!isPlaying || isProcessing) {
        timeoutId = setTimeout(captureAndProcess, 150);
        return;
      }

      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.readyState < 2) {
        timeoutId = setTimeout(captureAndProcess, 150);
        return;
      }

      isProcessing = true;
      const t0 = performance.now();

      try {
        const ctx = canvas.getContext('2d');
        if (ctx) {
          // Draw video frame to canvas
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

          // Get Base64 image
          const base64Data = canvas.toDataURL('image/jpeg', 0.65);

          const res = await fetch('/api/process-live-frame', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              image_base64: base64Data,
              timestamp: Date.now() / 1000,
            }),
          });

          if (res.ok) {
            const data: LiveFrameResult = await res.json();
            setFramesCount((f) => f + 1);
            setNarrative(data.narrative);
            setDistribution(data.distribution);
            setActiveState(data.active_state);
            setKinematics({
              torsoAngle: data.torso_angle,
              relativeHeight: data.relative_body_height,
              motionIntensity: data.motion_intensity,
              motionlessDuration: data.motionless_duration,
            });

            if (data.incidents && data.incidents.length > 0) {
              onIncidentTriggered();
            }

            // Draw skeleton & annotations on canvas over video
            if (showSkeleton && data.landmarks) {
              drawSkeleton(ctx, data.landmarks, data.bbox, data.active_state, canvas.width, canvas.height);
            }
          }
        }
      } catch (e) {
        // Network or frame error
      } finally {
        const dt = Math.round(performance.now() - t0);
        setLatencyMs(dt);
        isProcessing = false;
        timeoutId = setTimeout(captureAndProcess, 150);
      }
    };

    timeoutId = setTimeout(captureAndProcess, 200);
    return () => clearTimeout(timeoutId);
  }, [isPlaying, showSkeleton, onIncidentTriggered]);

  // Skeleton rendering helper
  const drawSkeleton = (
    ctx: CanvasRenderingContext2D,
    lms: Record<string, [number, number, number]>,
    bbox: [number, number, number, number],
    state: string,
    width: number,
    height: number
  ) => {
    // Determine color
    let strokeColor = '#10b981'; // Green for normal
    if (state.includes('FALL') || state === 'LYING_ON_FLOOR') {
      strokeColor = '#ef4444'; // Red for fall
    } else if (state === 'SITTING') {
      strokeColor = '#f59e0b'; // Amber for sitting
    } else if (state.includes('LYING')) {
      strokeColor = '#38bdf8'; // Blue for resting
    }

    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = 3;
    ctx.fillStyle = '#ffffff';

    // Skeleton bone connections
    const bones = [
      ['left_shoulder', 'right_shoulder'],
      ['left_shoulder', 'left_elbow'],
      ['left_elbow', 'left_wrist'],
      ['right_shoulder', 'right_elbow'],
      ['right_elbow', 'right_wrist'],
      ['left_shoulder', 'left_hip'],
      ['right_shoulder', 'right_hip'],
      ['left_hip', 'right_hip'],
      ['left_hip', 'left_knee'],
      ['left_knee', 'left_ankle'],
      ['right_hip', 'right_knee'],
      ['right_knee', 'right_ankle'],
    ];

    bones.forEach(([k1, k2]) => {
      if (lms[k1] && lms[k2]) {
        const [x1, y1] = lms[k1];
        const [x2, y2] = lms[k2];
        ctx.beginPath();
        ctx.moveTo(x1 * width, y1 * height);
        ctx.lineTo(x2 * width, y2 * height);
        ctx.stroke();
      }
    });

    // Draw joints
    Object.values(lms).forEach(([x, y]) => {
      ctx.beginPath();
      ctx.arc(x * width, y * height, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    });

    // Draw Bounding Box
    if (bbox && bbox[2] > bbox[0]) {
      const [ymin, xmin, ymax, xmax] = bbox;
      const bx = xmin * width;
      const by = ymin * height;
      const bw = (xmax - xmin) * width;
      const bh = (ymax - ymin) * height;

      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(bx, by, bw, bh);

      // Label Tag
      ctx.fillStyle = strokeColor;
      ctx.fillRect(bx, Math.max(0, by - 22), Math.min(180, bw + 40), 22);
      ctx.fillStyle = '#000000';
      ctx.font = 'bold 11px JetBrains Mono';
      ctx.fillText(`person_01: ${state}`, bx + 6, Math.max(14, by - 7));
    }
  };

  // Top active item from distribution
  const topActive = distribution[0] || { label: 'UNCLEAR', percent: 0 };
  const isEmergency = topActive.label.includes('FALL') || activeState.includes('FALL');

  return (
    <div className="bg-black border border-slate-800 rounded-lg overflow-hidden flex flex-col font-mono text-xs shadow-2xl">
      {/* Top Half: Video Screen & Player */}
      <div className="relative bg-slate-950 aspect-video w-full flex items-center justify-center overflow-hidden">
        {/* Real HTML Video element */}
        <video
          ref={videoRef}
          playsInline
          autoPlay
          muted
          className={`w-full h-full object-cover ${sourceMode === 'simulation' ? 'hidden' : 'block'}`}
        />

        {/* Canvas overlay for drawing skeletons and fallback frames */}
        <canvas
          ref={canvasRef}
          width={640}
          height={360}
          className={`absolute inset-0 w-full h-full object-cover ${sourceMode === 'simulation' ? 'block' : 'pointer-events-none'}`}
        />

        {/* Camera Permission Alert */}
        {cameraError && (
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur flex flex-col items-center justify-center p-6 text-center z-20">
            <AlertTriangle className="w-8 h-8 text-amber-400 mb-2" />
            <p className="text-slate-200 font-semibold mb-2">{cameraError}</p>
            <div className="flex space-x-3 mt-2">
              <button
                onClick={() => setSourceMode('sample')}
                className="px-3 py-1.5 rounded bg-sky-600 hover:bg-sky-500 text-white font-medium text-xs transition-colors"
              >
                Switch to Sample Video Footage
              </button>
              <button
                onClick={startWebcam}
                className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-xs transition-colors"
              >
                Retry Webcam Permission
              </button>
            </div>
          </div>
        )}

        {/* Source Mode Selector & Overlay Controls */}
        <div className="absolute top-3 left-3 flex items-center space-x-2 z-10 bg-slate-900/90 backdrop-blur px-2 py-1 rounded border border-slate-800">
          <button
            onClick={() => setSourceMode('webcam')}
            className={`px-2 py-1 rounded text-[11px] font-semibold flex items-center space-x-1 ${
              sourceMode === 'webcam' ? 'bg-sky-500 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Camera className="w-3.5 h-3.5" />
            <span>MY WEBCAM (LIVE)</span>
          </button>

          <button
            onClick={() => setSourceMode('sample')}
            className={`px-2 py-1 rounded text-[11px] font-semibold flex items-center space-x-1 ${
              sourceMode === 'sample' ? 'bg-sky-500 text-white' : 'text-slate-400 hover:text-white'
            }`}
          >
            <Video className="w-3.5 h-3.5" />
            <span>SAMPLE FOOTAGE</span>
          </button>
        </div>

        {/* Play/Pause & Skeleton Toggle */}
        <div className="absolute top-3 right-3 flex items-center space-x-2 z-10">
          <button
            onClick={() => setShowSkeleton(!showSkeleton)}
            className="p-1.5 rounded bg-slate-900/90 border border-slate-800 text-slate-300 hover:text-white"
            title="Toggle Skeleton Overlay"
          >
            {showSkeleton ? <Eye className="w-3.5 h-3.5 text-sky-400" /> : <EyeOff className="w-3.5 h-3.5 text-slate-500" />}
          </button>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="p-1.5 rounded bg-slate-900/90 border border-slate-800 text-slate-300 hover:text-white"
            title={isPlaying ? 'Pause Feed' : 'Resume Feed'}
          >
            {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 text-emerald-400" />}
          </button>
        </div>

        {/* Live Watermark Indicator */}
        <div className="absolute bottom-3 left-3 bg-slate-950/80 px-2 py-0.5 rounded text-[10px] text-slate-400 border border-slate-800">
          MODE: <span className="text-emerald-400 font-bold uppercase">{sourceMode}</span> | FPS: <span className="text-slate-200">~10</span> | INFERENCE: <span className="text-sky-400">{latencyMs}MS</span>
        </div>
      </div>

      {/* Bottom Half: Exact Tactical Terminal HUD As Seen in Video */}
      <div className="p-5 bg-black text-slate-200 flex flex-col space-y-4 border-t border-slate-900">
        {/* 1. Situation Narrative Banner */}
        <div className="text-xs uppercase tracking-wide font-mono text-slate-300 leading-relaxed min-h-[38px] border-b border-slate-900 pb-3">
          {narrative}
        </div>

        {/* 2. Top Stats Bar: TIME, FRAMES, EST. COST */}
        <div className="grid grid-cols-3 text-xs border-b border-slate-900 pb-3 text-slate-400 font-mono">
          <div>
            <div className="text-[10px] text-slate-500 uppercase">TIME</div>
            <div className="text-sm font-bold text-slate-200">{String(elapsedSeconds).padStart(3, '0')} S</div>
          </div>
          <div>
            <div className="text-[10px] text-slate-500 uppercase">FRAMES</div>
            <div className="text-sm font-bold text-slate-200">{String(framesCount).padStart(4, '0')}</div>
          </div>
          <div>
            <div className="text-[10px] text-slate-500 uppercase">EST. COST / USD</div>
            <div className="text-sm font-bold text-emerald-400">$0.000000 (LOCAL)</div>
          </div>
        </div>

        {/* 3. High-Salience Active State Banner (Red for Fall, White for Normal) */}
        <div
          className={`py-2 px-3 rounded font-bold text-sm tracking-wider flex items-center justify-between ${
            isEmergency
              ? 'bg-rose-600 text-white'
              : 'bg-white text-black'
          }`}
        >
          <span className="font-mono">{topActive.percent.toFixed(1)}%</span>
          <span className="uppercase">{topActive.label}</span>
        </div>

        {/* 4. Activity & Posture Distribution Breakdown Table */}
        <div className="space-y-1.5 pt-1">
          {distribution.slice(1).map((item, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between py-1.5 px-3 rounded bg-[#121212] hover:bg-[#1a1a1a] border border-[#222222] font-mono text-xs text-slate-300"
            >
              <span className="font-semibold">{item.percent.toFixed(1)}%</span>
              <span className="uppercase tracking-wide">{item.label}</span>
            </div>
          ))}
        </div>

        {/* 5. Bottom Status Line Exactly As Seen in Video */}
        <div className="border-t border-slate-900 pt-3 flex items-center justify-between text-[11px] font-mono text-slate-500 uppercase tracking-wider">
          <div>
            {kinematics.motionIntensity > 0.04 ? 'MOVEMENT / POSTURE CHANGE' : 'NO CLEAR CHANGE'} / {latencyMs} MS
          </div>
          <div>
            TORSO: {kinematics.torsoAngle.toFixed(0)} DEG | HEIGHT: {kinematics.relativeHeight.toFixed(2)}
          </div>
        </div>

        {/* Simulation Shortcut Controls */}
        <div className="border-t border-slate-900/80 pt-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">
            Simulate Behavioral Scenarios (Click to Inject Kinematics):
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <button
              onClick={() => onTriggerScenario('bed')}
              className="py-1.5 px-2 rounded bg-slate-900 hover:bg-slate-800 text-sky-400 border border-slate-800 text-[11px]"
            >
              Bed Resting
            </button>
            <button
              onClick={() => onTriggerScenario('fall')}
              className="py-1.5 px-2 rounded bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 border border-rose-900/60 text-[11px]"
            >
              Sudden Fall
            </button>
            <button
              onClick={() => onTriggerScenario('failed_stand')}
              className="py-1.5 px-2 rounded bg-slate-900 hover:bg-slate-800 text-amber-400 border border-slate-800 text-[11px]"
            >
              Failed Rising x2
            </button>
            <button
              onClick={() => onTriggerScenario('wandering')}
              className="py-1.5 px-2 rounded bg-slate-900 hover:bg-slate-800 text-yellow-400 border border-slate-800 text-[11px]"
            >
              Restricted Area
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
