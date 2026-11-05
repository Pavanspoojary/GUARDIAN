import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Eye, EyeOff, Play, Pause, AlertCircle, RefreshCw } from 'lucide-react';
import { LiveFrameResult, ActivityDistributionItem } from '../types';

interface LiveMonitorProps {
  onIncidentTriggered: () => void;
}

export const LiveMonitor: React.FC<LiveMonitorProps> = ({ onIncidentTriggered }) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [showSkeleton, setShowSkeleton] = useState<boolean>(true);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [cameraReady, setCameraReady] = useState<boolean>(false);

  // Telemetry HUD states
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [framesCount, setFramesCount] = useState<number>(0);
  const [latencyMs, setLatencyMs] = useState<number>(28);
  const [narrative, setNarrative] = useState<string>('INITIALIZING DETERMINISTIC SURVEILLANCE PIPELINE...');
  const [distribution, setDistribution] = useState<ActivityDistributionItem[]>([
    { label: 'STANDING', percent: 85.0 },
    { label: 'WALKING', percent: 10.0 },
    { label: 'SITTING', percent: 5.0 },
    { label: 'UNCLEAR / OTHER', percent: 0.0 },
    { label: 'LYING / RESTING', percent: 0.0 },
    { label: 'POSSIBLE FALL · REVIEW', percent: 0.0 },
    { label: 'NO PERSON VISIBLE', percent: 0.0 },
  ]);
  const [activeState, setActiveState] = useState<string>('STANDING');
  const [kinematics, setKinematics] = useState({
    torsoAngle: 5.0,
    relativeHeight: 0.88,
    motionIntensity: 0.02,
    motionlessDuration: 0.0,
  });

  // Start webcam
  const startWebcam = useCallback(async () => {
    setCameraError(null);
    setCameraReady(false);

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
          videoRef.current?.play().then(() => {
            setCameraReady(true);
            setIsPlaying(true);
          }).catch((err) => {
            console.warn('Webcam play error:', err);
          });
        };
      }
    } catch (err: any) {
      console.warn('Webcam permission error:', err);
      setCameraError('Camera access required. Please allow webcam permission in your browser prompt.');
    }
  }, []);

  // Stop webcam
  const stopWebcam = useCallback(() => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((track) => track.stop());
      videoRef.current.srcObject = null;
    }
    setCameraReady(false);
  }, []);

  // Mount webcam on startup
  useEffect(() => {
    startWebcam();
    return () => {
      stopWebcam();
    };
  }, [startWebcam, stopWebcam]);

  // Elapsed timer
  useEffect(() => {
    const timer = setInterval(() => {
      if (isPlaying && cameraReady) {
        setElapsedSeconds((s) => s + 1);
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [isPlaying, cameraReady]);

  // Frame processing loop
  useEffect(() => {
    let timeoutId: any;
    let isProcessing = false;

    const captureAndProcess = async () => {
      if (!isPlaying || isProcessing) {
        timeoutId = setTimeout(captureAndProcess, 120);
        return;
      }

      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.readyState < 2) {
        timeoutId = setTimeout(captureAndProcess, 120);
        return;
      }

      isProcessing = true;
      const t0 = performance.now();

      try {
        const ctx = canvas.getContext('2d');
        if (ctx) {
          // Draw webcam video directly onto the single canvas
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

          // Get Base64 image snapshot
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

            // Draw skeleton & bounding box over canvas
            if (showSkeleton && data.landmarks) {
              drawSkeleton(ctx, data.landmarks, data.bbox, data.active_state, canvas.width, canvas.height);
            }
          }
        }
      } catch (e) {
        // Network or inference cycle
      } finally {
        const dt = Math.round(performance.now() - t0);
        setLatencyMs(dt);
        isProcessing = false;
        timeoutId = setTimeout(captureAndProcess, 120);
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
      ctx.fillRect(bx, Math.max(0, by - 22), Math.min(220, bw + 40), 22);
      ctx.fillStyle = '#000000';
      ctx.font = 'bold 11px JetBrains Mono';
      ctx.fillText(`person_01: ${state}`, bx + 6, Math.max(14, by - 7));
    }
  };

  const topActive = distribution[0] || { label: 'UNCLEAR', percent: 0 };
  const isEmergency = topActive.label.includes('FALL') || activeState.includes('FALL');

  return (
    <div className="bg-black border border-slate-800 rounded-xl overflow-hidden flex flex-col font-mono text-xs shadow-2xl">
      {/* Hidden background video source for capturing frames */}
      <video
        ref={videoRef}
        playsInline
        autoPlay
        muted
        style={{ display: 'none' }}
      />

      {/* Top Portion: Clean Single Video Canvas with Tactical Overlays */}
      <div className="relative bg-black aspect-video w-full flex items-center justify-center overflow-hidden border-b border-slate-900">
        <canvas
          ref={canvasRef}
          width={640}
          height={480}
          className="w-full h-full object-contain block bg-black"
        />

        {/* Tactical Watermark Overlay */}
        <div className="absolute top-3 left-3 flex items-center space-x-2 z-10 bg-black/75 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-800">
          <span className={`w-2 h-2 rounded-full ${cameraReady ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`}></span>
          <span className="text-[11px] font-bold text-slate-200 tracking-wider">LIVE WEBCAM STREAM</span>
          <span className="text-slate-500">|</span>
          <span className="text-[10px] text-sky-400">{latencyMs}MS</span>
        </div>

        {/* View Controls: Skeleton Toggle & Pause/Play */}
        <div className="absolute top-3 right-3 flex items-center space-x-2 z-10">
          <button
            onClick={() => setShowSkeleton(!showSkeleton)}
            className="p-1.5 rounded-lg bg-black/80 backdrop-blur border border-slate-800 text-slate-300 hover:text-white transition-colors"
            title="Toggle Skeleton Tracking"
          >
            {showSkeleton ? <Eye className="w-4 h-4 text-sky-400" /> : <EyeOff className="w-4 h-4 text-slate-500" />}
          </button>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="p-1.5 rounded-lg bg-black/80 backdrop-blur border border-slate-800 text-slate-300 hover:text-white transition-colors"
            title={isPlaying ? 'Pause Surveillance' : 'Resume Surveillance'}
          >
            {isPlaying ? <Pause className="w-4 h-4 text-slate-300" /> : <Play className="w-4 h-4 text-emerald-400" />}
          </button>
        </div>

        {/* Camera Permission Alert if Blocked */}
        {cameraError && (
          <div className="absolute inset-0 bg-slate-950/90 backdrop-blur-md flex flex-col items-center justify-center p-6 text-center z-20">
            <AlertCircle className="w-10 h-10 text-amber-400 mb-3" />
            <p className="text-slate-200 font-semibold max-w-md mb-4 text-sm">{cameraError}</p>
            <button
              onClick={startWebcam}
              className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-medium text-xs transition-colors flex items-center space-x-2"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry Camera Permission</span>
            </button>
          </div>
        )}

        {/* Bottom Metadata Bar */}
        <div className="absolute bottom-2 left-3 bg-black/80 backdrop-blur px-2.5 py-1 rounded text-[10px] text-slate-400 border border-slate-800 flex items-center space-x-3">
          <div>FEED: <span className="text-emerald-400 font-bold">WEBCAM</span></div>
          <div>INFERENCE: <span className="text-sky-400">{latencyMs}MS</span></div>
          <div>RATE: <span className="text-slate-200">~10 FPS</span></div>
        </div>
      </div>

      {/* Bottom Portion: Tactical Terminal HUD */}
      <div className="p-5 bg-black text-slate-200 flex flex-col space-y-4">
        {/* 1. Situation Narrative Banner */}
        <div className="text-xs uppercase tracking-wide font-mono text-slate-300 leading-relaxed min-h-[38px] border-b border-slate-900 pb-3">
          {narrative}
        </div>

        {/* 2. Top Metric Grid: TIME, FRAMES, EST. COST */}
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
          className={`py-2.5 px-3.5 rounded-lg font-bold text-sm tracking-wider flex items-center justify-between transition-colors ${
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
              className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-[#111622] hover:bg-[#161c2d] border border-slate-900 font-mono text-xs text-slate-300 transition-colors"
            >
              <span className="font-semibold text-slate-400">{item.percent.toFixed(1)}%</span>
              <span className="uppercase tracking-wide text-slate-300">{item.label}</span>
            </div>
          ))}
        </div>

        {/* 5. Bottom Status Line */}
        <div className="border-t border-slate-900 pt-3 flex items-center justify-between text-[11px] font-mono text-slate-500 uppercase tracking-wider">
          <div>
            {kinematics.motionIntensity > 0.04 ? 'MOVEMENT / POSTURE CHANGE' : 'NO CLEAR CHANGE'} / {latencyMs} MS
          </div>
          <div>
            TORSO: {kinematics.torsoAngle.toFixed(0)} DEG | HEIGHT: {kinematics.relativeHeight.toFixed(2)}
          </div>
        </div>
      </div>
    </div>
  );
};
