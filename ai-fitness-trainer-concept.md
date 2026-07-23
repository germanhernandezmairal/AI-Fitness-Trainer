# 🏋️ AI Fitness Trainer — Project Concept

An AI-powered fitness coach that watches an athlete perform a movement, **evaluates the quality of their technique**, assigns a **performance score**, and returns **actionable tips** to help them improve.

> **Inspiration:** [Reference video](https://www.youtube.com/watch?v=Ae3SPjsXETc)

---

## 💡 The Idea

The application analyzes video of an athlete performing an exercise (e.g. a squat, push-up, or deadlift) and, using computer vision and deep learning, it:

1. **Detects body pose** — extracts skeletal keypoints (joints, limbs, angles) frame by frame.
2. **Evaluates the movement** — compares the athlete's form against correct-technique patterns.
3. **Scores the performance** — produces a quantitative score reflecting technique quality.
4. **Suggests improvements** — generates specific, human-readable tips ("keep your back straighter", "go deeper on the squat", "slow down the eccentric phase").

The goal is to give athletes instant, objective feedback that would normally require a personal trainer watching in real time.

---

## 👥 The Team

| Role | Person | Focus |
|------|--------|-------|
| **Data / AI** | Alejandro Hernández Mairal — *Data Scientist specialized in Deep Learning · Python & PyTorch · passionate about AI applications* · [github.com/Alherma7](https://github.com/Alherma7) | Pose estimation, movement evaluation models, scoring logic, feedback generation |
| **Fullstack** | *(You)* | Web application, front end, back end, database, infrastructure, deployment |

---

## 🛠️ Tech Stack & Tools

### 🤖 Data / AI Side

**Languages & Databases**

![Languages & Databases](https://skillicons.dev/icons?i=python,postgres,bash)

**AI, Machine Learning & Computer Vision**

![AI & ML](https://skillicons.dev/icons?i=pytorch,tensorflow,opencv,scikitlearn,huggingface,pandas,numpy)

**Tools & Environment**

![Tools](https://skillicons.dev/icons?i=git,github,docker,vscode,linux)

### 🌐 Fullstack Application Side

![Fullstack](https://skillicons.dev/icons?i=js,ts,react,nextjs,nodejs,express,fastapi,postgres,redis,docker,vscode,aws)

- **Front end:** JavaScript / TypeScript + React (often Next.js)
- **Back end:** Node/Express *or* Python/FastAPI
- **Database:** PostgreSQL
- **Caching:** Redis
- **Containerization:** Docker
- **Editor:** VS Code
- **Deployment:** AWS

---

## 🧩 How It Fits Together

```
                    ┌─────────────────────────────┐
   Athlete's        │   Front End (React/Next.js) │
   video   ───────► │   upload · results · tips   │
                    └──────────────┬──────────────┘
                                   │  REST / API calls
                    ┌──────────────▼──────────────┐
                    │  Back End (FastAPI / Express)│
                    │  auth · orchestration · API  │
                    └──────┬───────────────┬───────┘
                           │               │
              ┌────────────▼──────┐   ┌────▼─────────────┐
              │  AI Service       │   │  PostgreSQL      │
              │  (PyTorch model)  │   │  users · results │
              │  pose → score →   │   │  history         │
              │  feedback         │   └──────────────────┘
              └───────┬───────────┘
                      │  (heavy results cached)
                ┌─────▼─────┐
                │   Redis   │
                └───────────┘
```

**Responsibility split**

- **Alejandro (AI):** pose-estimation pipeline (OpenCV + PyTorch/TensorFlow), technique evaluation, the scoring model, and the feedback/tips generation — packaged as a service the back end can call.
- **You (Fullstack):** the web app that lets users upload/record video, calls the AI service, stores and displays results, manages accounts and history, and handles containerization + AWS deployment.

---

## 🎯 Core Features (MVP)

- [ ] Upload or record a video of an exercise
- [ ] Pose detection and movement analysis
- [ ] Numerical technique score per attempt
- [ ] Personalized improvement tips
- [ ] User accounts with a history of past attempts and progress over time

## 🚀 Possible Extensions

- Real-time analysis via webcam (live feedback)
- Support for multiple exercise types with per-exercise scoring criteria
- Rep counting and tempo tracking
- Progress dashboards and trend charts
- Comparison against an athlete's own previous best

---

## 📚 References

- Concept inspiration: <https://www.youtube.com/watch?v=Ae3SPjsXETc>
- AI collaborator: <https://github.com/Alherma7>
