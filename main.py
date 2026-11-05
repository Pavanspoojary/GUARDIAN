"""SENTINEL CLI and entrypoint for running server and processing video streams."""

from __future__ import annotations

import argparse
import sys
import time
import uvicorn
import cv2

from sentinel.perception.video_source import VideoSource
from sentinel.perception.pose_estimator import MediaPipePoseEstimator, SyntheticPoseEstimator
from sentinel.system import SentinelEngine


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Launch the FastAPI server."""
    print(f"Starting SENTINEL Decision Engine Server on http://{host}:{port}")
    uvicorn.run("sentinel.api.main:app", host=host, port=port, reload=False)


def process_video_stream(source: str, rules_dir: str = "configs/rules") -> None:
    """Run real-time video processing from camera or video file."""
    print(f"Initializing SENTINEL video processing pipeline for source: {source}")
    try:
        pose_estimator = MediaPipePoseEstimator()
        print("MediaPipe Pose Landmarker initialized successfully.")
    except Exception as e:
        print(f"MediaPipe initialization warning: {e}. Falling back to Synthetic provider.")
        pose_estimator = SyntheticPoseEstimator()

    engine = SentinelEngine(
        pose_estimator=pose_estimator,
        rules_directory=rules_dir,
    )

    src = int(source) if source.isdigit() else source
    video = VideoSource(source=src)

    if not video.connect():
        print(f"Failed to connect to video source: {source}")
        return

    print("Connected to video stream. Processing frames (press Ctrl+C to stop)...")
    try:
        frame_idx = 0
        for frame, ts in video.stream():
            frame_idx += 1
            result = engine.process_frame(frame, timestamp=ts)

            if result["new_incidents"]:
                for inc in result["new_incidents"]:
                    print(
                        f"[{time.strftime('%X')}] [ALERT] Incident {inc['incident_id']} "
                        f"({inc['incident_type']}) - Risk: {inc['risk_level']} (Score: {inc['risk_score']:.2f})"
                    )
                    print(f"    Narrative: {inc['narrative']}")

            if frame_idx % 100 == 0:
                print(
                    f"Processed {frame_idx} frames. "
                    f"Active tracks: {result['active_tracks_count']}, "
                    f"Dropped frames: {video.dropped_frames}"
                )
    except KeyboardInterrupt:
        print("\nStopping SENTINEL video processing.")
    finally:
        video.release()
        engine.close()


def validate_rules(rules_dir: str = "configs/rules") -> None:
    """Validate all YAML rule definitions in the configuration directory."""
    from sentinel.engine.rule_engine import RuleEngine
    engine = RuleEngine()
    rules = engine.load_rules_from_directory(rules_dir)
    print(f"Successfully loaded and validated {len(rules)} rules from {rules_dir}:")
    for r in sorted(rules, key=lambda x: x.priority, reverse=True):
        status = "ENABLED" if r.enabled else "DISABLED"
        print(f"  - Priority {r.priority:3d} | [{r.risk_level.value:13s}] | {r.name:32s} | ({status})")


def main() -> None:
    parser = argparse.ArgumentParser(description="SENTINEL Deterministic Safety Engine")
    subparsers = parser.add_subparsers(dest="command")

    # Serve command
    server_parser = subparsers.add_parser("serve", help="Launch FastAPI server")
    server_parser.add_argument("--host", default="0.0.0.0", help="Binding host")
    server_parser.add_argument("--port", type=int, default=8000, help="Port")

    # Video command
    video_parser = subparsers.add_parser("process-video", help="Process video stream or file")
    video_parser.add_argument("--source", default="0", help="Camera index or video file path")
    video_parser.add_argument("--rules", default="configs/rules", help="Rules configuration directory")

    # Validate rules command
    subparsers.add_parser("validate-rules", help="Validate YAML safety rules")

    args = parser.parse_args()

    if args.command == "serve":
        run_server(host=args.host, port=args.port)
    elif args.command == "process-video":
        process_video_stream(source=args.source, rules_dir=args.rules)
    elif args.command == "validate-rules":
        validate_rules()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
