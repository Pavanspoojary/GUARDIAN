# SENTINEL — Deterministic Human Behaviour & Safety Decision Engine

SENTINEL is an advanced, offline-first, deterministic human behaviour monitoring and safety decision engine built in Python. Designed for eldercare and assisted-living environments, SENTINEL evaluates continuous physical kinematics, temporal state machines, and environmental context to identify safety events with explainable evidence chains.

---

## 1. Core Philosophy: Zero LLM Invariant

SENTINEL is engineered under a strict deterministic invariant:
- **Zero LLMs**: No OpenAI, Gemini, Claude, or probabilistic AI APIs.
- **Zero Generative AI**: No hallucinations, prompt drift, or unpredictable outcomes.
- **Zero Vector Databases or Embeddings**: No opaque semantic distance calculations.
- **Offline & Local-First**: Runs on local hardware without cloud connectivity or internet access.
- **Explainable Decisions**: Every alert traces to exact mathematical metrics, geometric angles, velocity differentials, duration timers, and evaluated counter-hypotheses.

Computer vision models (e.g., MediaPipe Pose Landmarker) are used strictly as sensory perception to extract body landmarks. All subsequent feature computation, activity classification, state tracking, risk assessment, and incident decision-making are implemented through deterministic Python code.

---

## 2. System Architecture

```text
+--------------------------------------------------------------------------+
|                        Layer 1: Video Intelligence                       |
|   OpenCV VideoCapture - Stream Reconnection - Frame Drop Detection       |
+--------------------------------------------------------------------------+
                                     |
+--------------------------------------------------------------------------+
|               Layer 2: Human Detection & Pose Estimation                 |
|   MediaPipe Pose Landmarker - Kalman Filter - Hungarian Algorithm        |
+--------------------------------------------------------------------------+
                                     |
+--------------------------------------------------------------------------+
|                       Layer 3: Feature Extraction                        |
|   Torso Angles - Normalized Heights - Vertical Velocity - Motion Metric  |
+--------------------------------------------------------------------------+
                                     |
+--------------------------------------------------------------------------+
|                       Layer 4: Activity Recognition                      |
|   STANDING - WALKING - SITTING - LYING - LYING_ON_FLOOR - TRANSITIONING  |
|   Hysteresis Smoothing - Multi-Frame Consensus - High-Salience Override  |
+--------------------------------------------------------------------------+
                                     |
+--------------------------------------------------------------------------+
|                     Layer 5: Temporal State Machine                      |
|   State Durations - Transition Sequences - Failed Standing Counter       |
+--------------------------------------------------------------------------+
                                     |
+--------------------------------------------------------------------------+
|                  The Core: Deterministic Decision Engine                 |
|   Pydantic YAML Rules - Condition Registry - Priority & Suppression      |
|   Multi-Factor Risk Assessor - Explanation Engine & Hypothesis Auditor   |
+--------------------------------------------------------------------------+
                                     |
+--------------------------------------------------------------------------+
|                 Statistical Intelligence & Event Lifecycle               |
|   Rolling Medians & MAD - Anomaly Detection - Incident Correlator        |
|   DETECTED -> UNDER_REVIEW -> ACKNOWLEDGED -> RESOLVED Audit Trail       |
+--------------------------------------------------------------------------+
                                     |
+--------------------------------------------------------------------------+
|                   Presentation Layer: API & Dashboard                    |
|   FastAPI REST & WebSocket Server - React + Vite Real-Time Dashboard     |
+--------------------------------------------------------------------------+
```

---

## 3. Five Layers of Processing

### Layer 1: Video Intelligence (`sentinel.perception.video_source`)
- Supports local webcams, RTSP IP camera streams, recorded video files (`.mp4`, `.avi`), and procedural synthetic video generators.
- Auto-reconnect handling for dropped feeds and camera disconnections.

### Layer 2: Perception & Tracking (`sentinel.perception.tracker`)
- **Pose Estimator Abstraction**: `PoseEstimatorBase` interface decouples perception from the decision engine.
- **Kalman Filtering & Hungarian Assignment**: Maintains persistent track identifiers across frames using IoU overlap cost matrices via `scipy.optimize.linear_sum_assignment`.

### Layer 3: Feature Extraction (`sentinel.activity.feature_extractor`)
- Calculates normalized physical metrics independent of camera resolution:
  - **Torso Angle**: Angle of shoulder-to-hip vector relative to the vertical axis (0 deg = upright, 90 deg = horizontal).
  - **Relative Body Height**: Normalized vertical span relative to camera frame and standing baseline.
  - **Vertical Velocity ($dY/dt$)**: Downward displacement rate (positive = dropping).
  - **Vertical Acceleration ($d^2Y/dt^2$)**: Kinematic impact marker.
  - **Movement Velocity**: 2D horizontal ambulation speed.
  - **Motion Intensity**: Mean Euclidean displacement of all body landmarks across frames.
  - **Floor Proximity**: Distance between lowest joints (ankles) and calibrated floor plane.

### Layer 4: Deterministic Activity Classifier (`sentinel.activity.activity_classifier`)
- Classifies human state: `STANDING`, `WALKING`, `SITTING`, `LYING`, `LYING_ON_FLOOR`, `TRANSITIONING`, `UNKNOWN`.
- Employs temporal hysteresis with sliding consensus windows to eliminate single-frame posture jitter.
- High-salience override: Sudden vertical descents ($>0.4$ m/s) or recumbent postures immediately bypass smoothing to ensure rapid detection.

### Layer 5: Temporal State Machine (`sentinel.activity.state_machine`)
- Tracks per-person continuous duration in active state, transition timestamps, sequence history, and motionless timers.
- Distinguishes:
  - `WALKING -> SITTING -> LYING (in BED)` (Intentional Resting)
  - `WALKING -> SUDDEN_DESCENT -> LYING_ON_FLOOR -> STILLNESS` (Urgent Fall Incident)
- Detects repeated failed rising attempts: `SITTING -> TRANSITIONING -> SITTING` within brief intervals.

---

## 4. The Deterministic Decision Engine

### Rule Configuration (`configs/rules/*.yaml`)
Rules are defined declaratively in YAML and validated via Pydantic:
```yaml
id: possible_fall_detection
name: Possible Fall Detection
priority: 100
risk_level: URGENT
base_risk_score: 0.90
cooldown_seconds: 120.0
suppresses:
  - general_prolonged_inactivity
recommended_action: Immediate caregiver check required. Verify responsiveness.

conditions:
  all_of:
    - metric: activity_state
      operator: in
      value: ["LYING_ON_FLOOR", "LYING"]
    - metric: torso_angle
      operator: gte
      value: 60.0
    - any_of:
        - metric: seconds_since_sudden_descent
          operator: lte
          value: 10.0
        - metric: peak_descent_velocity
          operator: gte
          value: 0.8
    - none_of:
        - metric: zone_name
          operator: in
          value: ["BED", "SOFA"]
```

### Priority, Suppression & Cooldowns
- **Priority Scheduling**: Rules are evaluated in descending priority order.
- **Rule Suppression**: High-priority events suppress redundant lower-severity alerts (e.g. `possible_fall_detection` suppresses `general_prolonged_inactivity`).
- **Cooldown Registers**: Prevents alert flooding by enforcing per-person cooldown timers on triggered rules.

### Multi-Factor Risk Assessment (`sentinel.engine.risk_assessor`)
Computes deterministic risk scores bounded in $[0.0, 1.0]$:
$$ \text{Score} = \text{clamp}\left( \text{BaseScore} \times \left(0.4 + 0.6 \times \frac{\sum w_i}{\sum W}\right) \times \text{Confidence} \times \text{StillnessMultiplier} \times \text{NightMultiplier}, 0.0, 1.0 \right) $$

Mapped directly to deterministic levels:
- `0.00 - 0.20`: `NORMAL`
- `0.21 - 0.40`: `INFORMATIONAL`
- `0.41 - 0.65`: `WATCH`
- `0.66 - 0.85`: `REVIEW`
- `0.86 - 1.00`: `URGENT`

### Explanation Engine & Counter-Hypothesis Testing
Every event includes a human-readable explanation and transparent evaluation of rejected hypotheses:
- E.g., *"Lying on bed ruled out because person location is outside configured bed zone; Intentional posture change ruled out because vertical drop velocity was 1.45 m/s exceeding controlled transition thresholds."*

---

## 5. First Policy Pack: 10 Elderly Safety Policies

| Policy ID | Name | Priority | Risk Level | Description |
|---|---|---|---|---|
| `possible_fall_detection` | Possible Fall Detection | 100 | `URGENT` | Rapid vertical descent followed by recumbent posture outside furniture |
| `prolonged_floor_inactivity` | Prolonged Floor Inactivity | 95 | `URGENT` | Motionless floor position exceeding safety threshold (>=45s) |
| `camera_obstruction_failure` | Camera Obstruction / Failure | 90 | `REVIEW` | Hardware disconnection, black frames, or covered lens |
| `restricted_zone_crossing` | Restricted Zone Breach | 85 | `REVIEW` | Coordinates intersect staircases, utility areas, or hazard zones |
| `repeated_failed_standing` | Repeated Failed Standing | 80 | `REVIEW` | 2+ consecutive failed rising attempts from chair or floor |
| `unexpected_person_disappearance` | Unexpected Disappearance | 75 | `REVIEW` | Resident disappears from camera view outside known doors |
| `nighttime_bed_exit` | Nighttime Bed Exit | 70 | `WATCH` | Transitioning from bed to standing/walking during vulnerable hours |
| `nighttime_movement_monitoring` | Extended Nighttime Movement | 60 | `WATCH` | Sustained ambulation during sleeping hours |
| `abnormal_activity_sequence` | Abnormal Activity Sequence | 55 | `WATCH` | Erratic restlessness or rapid postural switching at night |
| `general_prolonged_inactivity` | Unexpected Inactivity | 50 | `REVIEW` | Extended daytime stillness outside sleeping area |

---

## 6. Behavioural Baselines & Statistical Intelligence

Uses non-parametric robust statistics without neural networks or LLMs:
- **Rolling Medians & Median Absolute Deviation (MAD)**:
  $$ \text{MAD} = \text{median}(|X_i - \tilde{X}|) $$
- **Modified Z-Score**:
  $$ M_i = \frac{0.6745 \times (X_i - \tilde{X})}{\text{MAD}} $$
- Establishes personal diurnals across 24 hourly bins. Requires minimum configurable sample days ($N \ge 3$) before flagging deviations.
- Explicit non-clinical guardrail: Statistical deviations are flagged strictly as welfare check suggestions, never as medical diagnoses.

---

## 7. Event Lifecycle & Caregiver Audit Trail

Safety events transition through a formal audited lifecycle:
$$\text{DETECTED} \longrightarrow \text{UNDER\_REVIEW} \longrightarrow \text{ACKNOWLEDGED} \longrightarrow \text{RESOLVED}$$

- **Event Correlation**: Merges proximate atomic events into unified multi-observation incidents.
- **Escalation Monitor**: Unacknowledged `URGENT` incidents trigger supervisor alerts if unattended beyond configurable timeout ($60$s).
- **Audit Log**: Immutable database records of every event creation, state transition, and caregiver operator acknowledgment.

---

## 8. Installation & Quickstart

### Prerequisites
- Python 3.10+ (Python 3.11 recommended)
- Node.js 18+ and npm (for dashboard)

### Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Validate Configured Safety Rules
```bash
python main.py validate-rules
```

### Launch the Complete System (API & React Dashboard)
```bash
python main.py serve --port 8000
```
Open your browser at `http://localhost:8000` to view the live dashboard.

### Process a Video File or Camera Feed
```bash
python main.py process-video --source 0               # Live camera
python main.py process-video --source path/video.mp4  # Video file
```

---

## 9. Automated Test Suite

Run the full deterministic test suite:
```bash
pytest tests -v
```

### Verifiable Test Coverage:
1. `tests/test_fall_sequences.py`: Verifies distinction between intentional bed resting and sudden accidental falls.
2. `tests/test_activity_states.py`: Verifies state machine duration timers, transition triggers, and failed standing attempts.
3. `tests/test_temporal_rules.py`: Verifies midnight wrap-around time windows and prolonged floor inactivity.
4. `tests/test_event_escalation.py`: Verifies cooldown alert deduplication and high-priority rule suppression.
5. `tests/test_vision_pipeline.py`: Verifies geometry calculations, Kalman multi-person tracking, and end-to-end perception pipeline.
6. `tests/test_intelligence_and_events.py`: Verifies median/MAD baselines, anomaly detection, event correlation, and escalation.
7. `tests/test_api.py`: Verifies FastAPI REST endpoints, rule toggling, simulation, and dashboard static serving.

---

## 10. Compliance & Ethical Boundaries

- **Local Processing**: Video processing runs on-premise without cloud transmission.
- **Privacy by Design**: Telemetry stores lightweight numerical coordinates and state history, not raw continuous video.
- **Non-Diagnostic Notice**: SENTINEL is a decision-support and behavioral awareness system. It does not provide medical diagnoses and does not replace emergency medical personnel or clinical equipment.
