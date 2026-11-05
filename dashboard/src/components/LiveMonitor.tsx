import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Eye, EyeOff, Play, Pause, AlertCircle, RefreshCw, Maximize2, Minimize2, Activity, ShieldAlert, ChevronLeft, ChevronRight } from 'lucide-react';
import { LiveFrameResult, ActivityDistributionItem, Incident } from '../types';

interface LiveMonitorProps {
  onIncidentTriggered: () => void;
  activeIncidents?: Incident[];
  onAcknowledge?: (incidentId: string, operator: string, notes: string) => Promise<void>;
  onResolve?: (incidentId: string, operator: string, notes: string) => Promise<void>;
}

interface TelemetryState {
  framesCount: number;
  latencyMs: number;
  adaptiveFps: number;
  narrative: string;
  distribution: ActivityDistributionItem[];
  activeState: string;
  torsoAngle: number;
  relativeHeight: number;
  motionIntensity: number;
  motionlessDuration: number;
}

export const LiveMonitor: React.FC<LiveMonitorProps> = ({
  onIncidentTriggered,
  activeIncidents = [],
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const offscreenCanvasRef = useRef<HTMLCanvasElement | null>(null);

  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [showSkeleton, setShowSkeleton] = useState<boolean>(true);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [cameraReady, setCameraReady] = useState<boolean>(false);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [isHudVisible, setIsHudVisible] = useState<boolean>(true);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);

  // Single batched telemetry state to eliminate multiple React re-renders per frame
  const [telemetry, setTelemetry] = useState<TelemetryState>({
    framesCount: 0,
    latencyMs: 14,
    adaptiveFps: 4,
    narrative: 'SYSTEM NOMINAL // SENSORY PIPELINE ACTIVE',
    distribution: [
      { label: 'SITTING', percent: 80.0 },
      { label: 'STANDING', percent: 15.0 },
      { label: 'WALKING', percent: 5.0 },
      { label: 'UNCLEAR / OTHER', percent: 0.0 },
      { label: 'LYING / RESTING', percent: 0.0 },
      { label: 'POSSIBLE FALL · REVIEW', percent: 0.0 },
      { label: 'NO PERSON VISIBLE', percent: 0.0 },
    ],
    activeState: 'SITTING',
    torsoAngle: 5.0,
    relativeHeight: 0.70,
    motionIntensity: 0.01,
    motionlessDuration: 0.0,
  });

  // Start webcam with efficient 640x480 resolution (zero sensor overload)
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
          if (canvasRef.current && videoRef.current) {
            canvasRef.current.width = videoRef.current.videoWidth || 640;
            canvasRef.current.height = videoRef.current.videoHeight || 480;
          }
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
      setCameraError('Camera access required. Please grant permission in your browser to start live surveillance.');
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

  // Toggle true browser fullscreen
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen().then(() => {
        setIsFullscreen(true);
      }).catch((e) => console.warn('Fullscreen failed:', e));
    } else {
      document.exitFullscreen().then(() => {
        setIsFullscreen(false);
      }).catch((e) => console.warn('Exit fullscreen failed:', e));
    }
  };

  useEffect(() => {
    const handleFsChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFsChange);
    return () => document.removeEventListener('fullscreenchange', handleFsChange);
  }, []);

  // Mount webcam on startup
  useEffect(() => {
    startWebcam();
    return () => {
      stopWebcam();
    };
  }, [startWebcam, stopWebcam]);

  // Elapsed timer (1-second tick)
  useEffect(() => {
    const timer = setInterval(() => {
      if (isPlaying && cameraReady) {
        setElapsedSeconds((s) => s + 1);
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [isPlaying, cameraReady]);

  // High-efficiency frame loop: 4-5 FPS is optimal for human fall & posture tracking
  useEffect(() => {
    let timeoutId: any;
    let isProcessing = false;
    let lastMotionTimestamp = Date.now();

    // Create compact 256x256 offscreen canvas (matches MediaPipe's exact native tensor input)
    if (!offscreenCanvasRef.current) {
      const oc = document.createElement('canvas');
      oc.width = 256;
      oc.height = 256;
      offscreenCanvasRef.current = oc;
    }

    const captureAndProcess = async () => {
      if (!isPlaying || isProcessing) {
        timeoutId = setTimeout(captureAndProcess, 200);
        return;
      }

      const video = videoRef.current;
      const overlayCanvas = canvasRef.current;
      const offscreen = offscreenCanvasRef.current;
      if (!video || !overlayCanvas || !offscreen || video.readyState < 2) {
        timeoutId = setTimeout(captureAndProcess, 200);
        return;
      }

      isProcessing = true;
      const t0 = performance.now();

      // Adaptive efficiency: 4 FPS (250ms) when resting/sitting, 6 FPS (160ms) when moving
      const isStill = (Date.now() - lastMotionTimestamp) > 2500;
      const nextInterval = isStill ? 250 : 160;
      const currentFps = isStill ? 4 : 6;

      try {
        const offCtx = offscreen.getContext('2d', { willReadFrequently: false });
        if (offCtx) {
          offCtx.drawImage(video, 0, 0, offscreen.width, offscreen.height);

          // Asynchronous zero-copy binary JPEG blob (50% quality is optimal for pose landmarks, only ~5KB)
          offscreen.toBlob(async (blob) => {
            if (!blob) {
              isProcessing = false;
              timeoutId = setTimeout(captureAndProcess, nextInterval);
              return;
            }

            try {
              const res = await fetch('/api/process-live-frame-raw', {
                method: 'POST',
                headers: { 'Content-Type': 'application/octet-stream' },
                body: blob,
              });

              if (res.ok) {
                const data: LiveFrameResult = await res.json();
                const dt = Math.round(performance.now() - t0);

                if (data.motion_intensity > 0.03) {
                  lastMotionTimestamp = Date.now();
                }

                // Single batched state update per frame tick
                setTelemetry((prev) => ({
                  framesCount: prev.framesCount + 1,
                  latencyMs: dt,
                  adaptiveFps: currentFps,
                  narrative: data.narrative,
                  distribution: data.distribution,
                  activeState: data.active_state,
                  torsoAngle: data.torso_angle,
                  relativeHeight: data.relative_body_height,
                  motionIntensity: data.motion_intensity,
                  motionlessDuration: data.motionless_duration,
                }));

                if (data.incidents && data.incidents.length > 0) {
                  onIncidentTriggered();
                }

                // Render skeleton overlay
                renderOverlay(data.landmarks, data.bbox, data.active_state);
              }
            } catch (err) {
              // Frame dropped safely
            } finally {
              isProcessing = false;
              timeoutId = setTimeout(captureAndProcess, nextInterval);
            }
          }, 'image/jpeg', 0.45);
        } else {
          isProcessing = false;
          timeoutId = setTimeout(captureAndProcess, nextInterval);
        }
      } catch (e) {
        isProcessing = false;
        timeoutId = setTimeout(captureAndProcess, nextInterval);
      }
    };

    timeoutId = setTimeout(captureAndProcess, 200);
    return () => clearTimeout(timeoutId);
  }, [isPlaying, onIncidentTriggered]);

  // Transparent overlay renderer
  const renderOverlay = (
    lms: Record<string, [number, number, number]>,
    bbox: [number, number, number, number],
    state: string
  ) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!showSkeleton || !lms || Object.keys(lms).length === 0) {
      return;
    }

    const width = canvas.width;
    const height = canvas.height;

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

    // Draw landmark points
    Object.values(lms).forEach(([x, y]) => {
      ctx.beginPath();
      ctx.arc(x * width, y * height, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    });

    // Draw Tactical Bounding Box
    if (bbox && bbox[2] > bbox[0]) {
      const [ymin, xmin, ymax, xmax] = bbox;
      const bx = xmin * width;
      const by = ymin * height;
      const bw = (xmax - xmin) * width;
      const bh = (ymax - ymin) * height;

      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(bx, by, bw, bh);

      // Corner target brackets
      const cornerLen = Math.min(16, bw / 4, bh / 4);
      ctx.lineWidth = 3;

      // Top-left
      ctx.beginPath();
      ctx.moveTo(bx, by + cornerLen);
      ctx.lineTo(bx, by);
      ctx.lineTo(bx + cornerLen, by);
      ctx.stroke();

      // Top-right
      ctx.beginPath();
      ctx.moveTo(bx + bw - cornerLen, by);
      ctx.lineTo(bx + bw, by);
      ctx.lineTo(bx + bw, by + cornerLen);
      ctx.stroke();

      // Bottom-left
      ctx.beginPath();
      ctx.moveTo(bx, by + bh - cornerLen);
      ctx.lineTo(bx, by + bh);
      ctx.lineTo(bx + cornerLen, by + bh);
      ctx.stroke();

      // Bottom-right
      ctx.beginPath();
      ctx.moveTo(bx + bw - cornerLen, by + bh);
      ctx.lineTo(bx + bw, by + bh);
      ctx.lineTo(bx + bw, by + bh - cornerLen);
      ctx.stroke();

      // State Tag
      ctx.fillStyle = strokeColor;
      ctx.fillRect(bx, Math.max(0, by - 22), Math.min(200, bw + 40), 22);
      ctx.fillStyle = '#000000';
      ctx.font = 'bold 11px JetBrains Mono, monospace';
      ctx.fillText(`person_01: ${state}`, bx + 6, Math.max(15, by - 7));
    }
  };

  const topActive = telemetry.distribution[0] || { label: 'UNCLEAR', percent: 0 };
  const isEmergency = topActive.label.includes('FALL') || telemetry.activeState.includes('FALL');
  const urgentIncidents = activeIncidents.filter((i) => i.status !== 'RESOLVED');

  return (
    <div
      ref={containerRef}
      className={`relative bg-black w-full overflow-hidden flex flex-col font-mono text-xs select-none transition-all ${
        isFullscreen ? 'fixed inset-0 z-50 h-screen' : 'h-[calc(100vh-76px)] rounded-2xl border border-slate-800 shadow-2xl'
      }`}
    >
      {/* 1. Full Screen Video Layer (Native GPU-accelerated) */}
      <div className="relative w-full h-full flex items-center justify-center bg-black overflow-hidden">
        <video
          ref={videoRef}
          playsInline
          autoPlay
          muted
          className="w-full h-full object-cover"
        />

        {/* 2. Transparent Tactical Canvas Overlay directly on top */}
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full object-cover pointer-events-none z-10"
        />

        {/* Camera Permission Alert if Blocked */}
        {cameraError && (
          <div className="absolute inset-0 bg-slate-950/90 backdrop-blur-md flex flex-col items-center justify-center p-6 text-center z-30">
            <AlertCircle className="w-12 h-12 text-amber-400 mb-3" />
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

        {/* TOP RIGHT FLOATING VIEW CONTROLS & FULLSCREEN */}
        <div className="absolute top-4 right-4 z-20 flex items-center space-x-2">
          {urgentIncidents.length > 0 && (
            <div className="bg-rose-600/90 backdrop-blur text-white px-3 py-1.5 rounded-xl border border-rose-500 font-bold text-xs flex items-center space-x-1.5 animate-pulse shadow-lg">
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>{urgentIncidents.length} ALERT{urgentIncidents.length > 1 ? 'S' : ''}</span>
            </div>
          )}

          <button
            onClick={() => setShowSkeleton(!showSkeleton)}
            className="p-2 rounded-xl bg-black/80 backdrop-blur-md border border-slate-800 text-slate-300 hover:text-white hover:bg-slate-900 transition-colors shadow-lg"
            title="Toggle Skeleton Tracking Overlay"
          >
            {showSkeleton ? <Eye className="w-4 h-4 text-sky-400" /> : <EyeOff className="w-4 h-4 text-slate-500" />}
          </button>

          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="p-2 rounded-xl bg-black/80 backdrop-blur-md border border-slate-800 text-slate-300 hover:text-white hover:bg-slate-900 transition-colors shadow-lg"
            title={isPlaying ? 'Pause Feed' : 'Resume Feed'}
          >
            {isPlaying ? <Pause className="w-4 h-4 text-slate-300" /> : <Play className="w-4 h-4 text-emerald-400" />}
          </button>

          <button
            onClick={toggleFullscreen}
            className="p-2 rounded-xl bg-black/80 backdrop-blur-md border border-slate-800 text-sky-400 hover:text-white hover:bg-slate-900 transition-colors shadow-lg"
            title={isFullscreen ? 'Exit Fullscreen' : 'Enter Edge-to-Edge Fullscreen'}
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>

        {/* LEFT-SIDE VERTICAL TACTICAL TELEMETRY HUD DOCK */}
        {isHudVisible ? (
          <div className="absolute top-4 left-4 bottom-4 z-20 w-80 md:w-88 flex flex-col bg-black/85 backdrop-blur-xl border border-slate-800/90 rounded-2xl p-4 shadow-2xl transition-all overflow-hidden">
            {/* Top Bar of Left HUD */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
              <div className="flex items-center space-x-2 text-slate-200">
                <span className={`w-2.5 h-2.5 rounded-full ${cameraReady ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`}></span>
                <span className="font-bold tracking-wider text-[11px]">LIVE SURVEILLANCE</span>
              </div>

              <div className="flex items-center space-x-2">
                <span className="text-[10px] text-sky-400 font-semibold bg-sky-500/10 px-1.5 py-0.5 rounded border border-sky-500/30">
                  {telemetry.latencyMs}MS
                </span>
                <button
                  onClick={() => setIsHudVisible(false)}
                  className="text-slate-400 hover:text-white transition-colors p-1 rounded-lg hover:bg-slate-800"
                  title="Collapse HUD to Left"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Narrative Banner */}
            <div className="mt-3 text-[11px] uppercase tracking-wide font-mono text-slate-300 leading-relaxed bg-[#0b0f19] p-3 rounded-xl border border-slate-900 flex items-start space-x-2 shrink-0">
              <Activity className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
              <span className="line-clamp-3">{telemetry.narrative}</span>
            </div>

            {/* 2-Column Telemetry Metrics (TIME, FRAMES) */}
            <div className="grid grid-cols-2 gap-3 py-3 border-b border-slate-900 text-xs font-mono shrink-0">
              <div>
                <div className="text-[9px] text-slate-500 uppercase tracking-wider">TIME</div>
                <div className="text-sm font-bold text-slate-100">{String(elapsedSeconds).padStart(3, '0')} S</div>
              </div>
              <div>
                <div className="text-[9px] text-slate-500 uppercase tracking-wider">FRAMES</div>
                <div className="text-sm font-bold text-slate-100">{String(telemetry.framesCount).padStart(4, '0')}</div>
              </div>
            </div>

            {/* High-Salience Active State Banner */}
            <div className="py-2 shrink-0">
              <div
                className={`py-2 px-3.5 rounded-xl font-bold text-xs tracking-wider flex items-center justify-between transition-colors shadow-sm ${
                  isEmergency
                    ? 'bg-rose-600 text-white'
                    : 'bg-white text-black'
                }`}
              >
                <span className="font-mono text-sm">{topActive.percent.toFixed(1)}%</span>
                <span className="uppercase text-sm">{topActive.label}</span>
              </div>
            </div>

            {/* Vertical Posture Distribution Breakdown Stack */}
            <div className="flex-1 space-y-1.5 overflow-y-auto pr-1 py-1 min-h-0">
              {telemetry.distribution.slice(1).map((item, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between py-1.5 px-3 rounded-lg bg-[#111622] hover:bg-[#161c2d] border border-slate-900/80 font-mono text-xs text-slate-300 transition-colors"
                >
                  <span className="font-semibold text-slate-400">{item.percent.toFixed(1)}%</span>
                  <span className="uppercase tracking-wide truncate ml-2 text-slate-300">{item.label}</span>
                </div>
              ))}
            </div>

            {/* Kinematics Status Footer */}
            <div className="pt-3 border-t border-slate-900 flex flex-col space-y-1 text-[10px] text-slate-500 font-mono uppercase shrink-0">
              <div className="flex items-center justify-between text-slate-400">
                <span>{telemetry.motionIntensity > 0.03 ? 'MOVEMENT / POSTURE CHANGE' : 'NO CLEAR CHANGE'}</span>
                <span className="text-sky-400">~{telemetry.adaptiveFps} FPS</span>
              </div>
              <div className="flex items-center justify-between text-slate-500">
                <span>TORSO: {telemetry.torsoAngle.toFixed(0)}&deg;</span>
                <span>HEIGHT: {telemetry.relativeHeight.toFixed(2)}</span>
                <span>STILL: {telemetry.motionlessDuration.toFixed(1)}S</span>
              </div>
            </div>
          </div>
        ) : (
          /* Collapsed HUD Mini-Pill on Left */
          <div className="absolute top-4 left-4 z-20 flex items-center space-x-2 bg-black/85 backdrop-blur-md p-1.5 rounded-xl border border-slate-800 shadow-xl font-mono text-xs">
            <button
              onClick={() => setIsHudVisible(true)}
              className="p-1.5 rounded-lg bg-sky-500/20 text-sky-300 border border-sky-500/30 hover:bg-sky-500/30 transition-colors"
              title="Expand Telemetry HUD"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
            <div
              className={`px-3 py-1 rounded-lg font-bold text-xs uppercase ${
                isEmergency ? 'bg-rose-600 text-white' : 'bg-white text-black'
              }`}
            >
              {topActive.percent.toFixed(0)}% {topActive.label}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
