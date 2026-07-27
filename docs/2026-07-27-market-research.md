# Market Research — AI Fitness Trainer

**Date:** 2026-07-27
**Author:** Fullstack role (compiled with Claude)
**Purpose:** Survey of established products with a value proposition similar to ours
(video-based AI evaluation of exercise technique → score + feedback), to inform positioning,
differentiation, and the *memoria* (§1 Introducción, §2 Objetivos, §8 Costes).

---

## 1. Our value proposition (for reference)

Upload or record a video of an exercise → the system detects body pose, evaluates technique,
returns a **numeric score per attempt** and **actionable improvement tips**, and stores a
**history** so athletes can track progress. MVP: squat only, pre-recorded upload, asynchronous
analysis returning a per-rep report plus an annotated video.

---

## 2. Market segments

The space splits into two sub-segments. We sit primarily in **B**, but compete for attention
with **A**.

### A. Real-time / on-device form correction
Camera runs live; feedback appears mid-rep.

| Product | Positioning / notes |
|---------|--------------------|
| **Gymscore** | Positioned as the leading 2026 form-check app. Scores technique across 5 dimensions: bracing, posture, foot placement, range of motion, movement efficiency. Closest competitor to our value prop. |
| **SHRED** | Camera-based real-time feedback; among the most accurate. Tracks 17–25 skeletal joints. |
| **Forme** | Real-time correction; 17–25 joints, form-correction accuracy cited ~92%. |
| **AiKYNETIX** | Strongest option for live, rep-by-rep barbell analysis. |
| **Kemtai, Perch, Hawkin Dynamics** | Real-time form correction via computer vision / motion tracking. |
| **Tempo, Peloton (Guide)** | Use cameras/sensors to correct form mid-rep (hardware-assisted). |

### B. Upload-a-video analysis (our MVP model — pre-recorded, asynchronous)

| Product | Positioning / notes |
|---------|--------------------|
| **FormCheck AI** | Upload/analyze barbell lifts against biomechanical standards. |
| **CueForm AI** | Computer vision + pose estimation; compares key body points to biomechanical standards, detects small form issues on squats and barbell lifts. |

---

## 3. Common technology (validates our stack)

Almost all of these apps are built on the **same core pipeline we and Alejandro chose**:

- **MediaPipe** for real-time pose/landmark estimation.
- **OpenCV** for frame-by-frame video analysis.
- **Joint-angle computation** on key points (knees, hips, shoulders) to evaluate movement.
- Some add **YOLO** for detection.

**Takeaway:** our technical bet is mainstream and proven, not exotic. Alejandro's rules-based
angle-threshold prototype (`script.py`) mirrors exactly how the market builds v1, with a clean
path to a trained ML model later.

---

## 4. Pricing / positioning benchmarks

Consumer subscriptions (annual):

| Product | Approx. price/yr |
|---------|------------------|
| FitnessAI | ~$90 |
| Fitbod | ~$96 |
| SHRED | ~$100 |
| JuggernautAI (specialist coaching) | ~$350 |
| Budget tier (general) | $39–$130 |

The band is roughly **$39–$130/yr** for consumer apps, up to **~$350/yr** for specialist
coaching. Useful for the *memoria* cost/value discussion (§8), even though our project is not
launching commercially.

---

## 5. Gaps & differentiation opportunities

1. **Single-camera plane-of-motion limits.** A known, unsolved weakness across every product:
   one camera can't fully capture 3D movement (e.g. depth vs. forward lean ambiguity). An honest
   UX around **capture angle guidance** could differentiate and improve accuracy cheaply.
2. **Async "coach's report" vs. live buzzer.** Most consumer apps are real-time and closed. Our
   **asynchronous, upload-based, per-rep scored report with an annotated video and a transparent,
   extensible error catalog** reads more like a *coach's written breakdown* than a live alert —
   a defensible niche and a strong fit for a portfolio/TFG deliverable.
3. **Privacy-first handling of body video (GDPR / LOPDGDD).** Almost none of the competitors lead
   with data protection. Since we process **potentially biometric** data, a privacy-first design
   (consent, retention/deletion, encryption) is both a legal requirement (*memoria* §9) and a
   genuine differentiator in the EU market.
4. **Transparency & extensibility.** Open, documented error codes and an `algorithm_version`
   field (per Alejandro's CV design) make results explainable and comparable over time — most
   consumer apps are black boxes.

---

## 6. Implications for our project

- **Validation:** the segment is active and growing in 2026 → the problem is real and worth solving.
- **Differentiation:** don't try to out-real-time the incumbents. Lean into async depth-of-feedback,
  transparency, and EU-grade privacy.
- **Scope discipline:** competitors span many exercises; our MVP (squat only, extensible) is the
  right narrow wedge.

---

## Sources

- [Gymscore — Best AI Workout Form Check App 2026](https://www.gymscore.ai/blog/best-ai-workout-form-check-app-2026/)
- [Sensai — Best AI Workout Form Check Apps (2026): What Actually Works](https://www.sensai.fit/blog/best-ai-workout-form-check-apps-2026)
- [CueForm — 5 best apps for analyzing squat form](https://cueform.ai/posts/best-apps-analyzing-squat-form/)
- [Forge — Best AI Personal Trainer Apps 2026](https://forgetrainer.ai/blog/best-ai-personal-trainer-apps-2026)
- [Unite.AI — Best AI Tools for Personal Trainers (July 2026)](https://www.unite.ai/best-ai-tools-for-personal-trainers/)
- [Qubika — AI-Powered App for Exercise Technique (PoC)](https://qubika.com/blog/ai-computer-driven-pose-detection-proof-of-concept/)
- [TrueCoach — Top 9 AI Tools For Personal Trainers](https://truecoach.co/blog/top-9-ai-tools-that-revolutionize-personal-training/)
