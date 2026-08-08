# 🚀 Antigravity — Canvas LMS & Health Connect System Architecture

> **Complete System Documentation** for Canvas LMS API (`lms.vitonline.in`) Gamification Engine, Google Health Connect & Fitness Pipeline, and Cloud Synchronization Architecture.

---

## 🎯 1. Canvas LMS REST API Integration (`lms.vitonline.in`)

Antigravity converts your VIT Online Master of Science in Data Science degree into an automated, gamified XP engine. It scans active course modules, video viewings, weekly quizzes, assignments, and exams via the Canvas REST API.

### 🏛️ Architecture Overview

```
+-----------------------------------------------------------------------+
|                    VIT ONLINE CANVAS LMS PLATFORM                     |
|                      (https://lms.vitonline.in)                        |
+-----------------------------------------------------------------------+
                                   |
                  Canvas REST API (Bearer Token Auth)
                                   v
+-----------------------------------------------------------------------+
|                  CanvasLMSSync Engine (canvas_sync.py)                |
|  - Rate-limit Backoff (HTTP 429) & Link Header Pagination             |
|  - Dynamic Action Reward Matrix & Score Evaluation                    |
|  - Streak Multiplier Engine (Ms)                                      |
+-----------------------------------------------------------------------+
                                   |
        +--------------------------+--------------------------+
        |                                                     |
        v                                                     v
[SQLite system_solo.db]                            [Neon PostgreSQL Cloud]
canvas_completed_items                             pg_canvas_completed_items
        |                                                     |
        +--------------------------+--------------------------+
                                   v
                    [Antigravity Dashboard & UI]
                       /canvas Progress Page
```

---

### 🏆 Canvas LMS Action Reward Matrix

| LMS Activity Type | Base XP | Stat Boost | Criteria & Bonus Conditions |
| --- | --- | --- | --- |
| **Course Orientation / Reading Page** | **15 XP** | +1 INT | Viewing study materials or reading pages |
| **Lecture Video (10–35 mins)** | **25 XP** | +1 INT | Complete video playback tracking |
| **Weekly Feedback Survey** | **15 XP** | +1 WIL | Submitting mandatory weekly survey |
| **Q&A Discussion Contribution** | **30 XP** | +1 INT, +1 AGI | Posting a verified answer or question on discussion board |
| **Live Session Recording** | **40 XP** | +2 INT | Viewing full live session recording |
| **Weekly Quiz (20 pts)** | **100 XP** | +5 INT | Submitting a weekly quiz |
| 🎯 *Perfect Quiz Bonus* | **+20 XP** | +2 INT | **Condition:** Scoring 100% (score == max_score) |
| ⚡ *Early Bird Quiz Bonus* | **+25 XP** | +1 WIL | **Condition:** Submitting quiz $\ge 48$ hours before deadline |
| **Digital Assignment (50 pts)** | **350 XP** | +15 INT, +10 AGI | Submitting a major digital assignment / coding project |
| 🏆 **Continuous Assessment (CAT)** | **600 XP** | +25 INT, +15 WIL | Submitting the Mid-Term CAT Exam / End Term Evaluation |
| 👑 **Full Week Module Wipe** | **+100 XP** | +5 WIL | **Condition:** Completing 100% of a module's items |

---

### 🔥 Streak Multiplier Engine ($M_s$)

All Canvas LMS payouts are scaled dynamically by the player's consecutive daily streak ($M_s$):

$$M_s = 1.0 + \min\left(1.0, \frac{\text{Streak Days}}{30.0}\right)$$

$$XP_{\text{earned}} = \text{round}(XP_{\text{base}} \times M_s)$$

- **0-Day Streak:** $100\%$ XP Payout (Quiz = 100 XP, CAT = 600 XP)
- **15-Day Streak:** $150\%$ XP Payout (Quiz = 150 XP, CAT = 900 XP)
- **30+-Day Streak:** $200\%$ XP Payout (**Double XP!** Quiz = 200 XP, CAT = 1,200 XP!)

---

### 📡 API Endpoints Summary (`server.py`)

- `GET /canvas` — Serves interactive Canvas LMS dashboard page (`canvas.html`).
- `GET /api/canvas/status` — Checks token validity & connectivity to `lms.vitonline.in`.
- `GET /api/canvas/courses` — Returns all 16 active courses with XP earned and item counts.
- `GET /api/canvas/history` — Returns past item completion logs with XP breakdown.
- `POST /api/canvas/sync` — Triggers background sync across all courses.
- `GET /api/canvas/progress` — Returns live sync progress percentage (`0%` → `100%`), items scanned, and current course being processed for UI progress bar.

---

## 🏃‍♂️ 2. Google Health Connect & Walking Sync Pipeline

Integrates step counts, distance, active minutes, sleep, and resting heart rate into character stat progression and cognitive recovery.

### 📊 Metric to Attribute Mapping

| Health Vector | Real-World Activity | System Impact & Formula |
| --- | --- | --- |
| **Step Count & Distance** | Daily Road & Park Walks | $+10\text{ XP}$ and $+1\text{ WIL}$ per 1,000 steps |
| **Sleep Duration** | Overnight Recovery | Restores **Cognitive Energy** $E_t \to +35\%$ if sleep $\ge 7.0\text{ hrs}$ ($+15\%$ if $\ge 5.5\text{ hrs}$) |
| **Active Workout Minutes** | Gym Sessions & Running | $+2\text{ STR}$ and $+20\text{ XP}$ per 10 active mins |
| **Resting Heart Rate** | Cardiovascular Stress | Boosts **Heart ($\text{HRT}$)** stat by $+1$ if resting HR in 50–70 bpm range |

---

### 🔌 API Endpoint Specification (`POST /api/health_sync`)

#### Request Payload:
```json
{
  "steps": 8500,
  "distance_km": 6.2,
  "active_minutes": 45,
  "sleep_hours": 7.5,
  "resting_hr": 62,
  "log_date": "2026-08-08"
}
```

#### Response Payout:
```json
{
  "status": "SUCCESS",
  "log_date": "2026-08-08",
  "steps": 8500,
  "distance_km": 6.2,
  "active_minutes": 45,
  "sleep_hours": 7.5,
  "xp_awarded": 170,
  "wil_gained": 8,
  "str_gained": 8,
  "hrt_gained": 1,
  "energy_restored": 35.0
}
```

---

### 📱 Phone Automation Setup (MacroDroid / Tasker / Termux)

You can trigger an automated background payload from your mobile device every evening at 9:00 PM:

#### Termux / Tasker cURL Command:
```bash
curl -X POST "https://cryosoftware.vercel.app/api/health_sync" \
     -H "Content-Type: application/json" \
     -d '{
           "steps": 8500,
           "distance_km": 6.2,
           "active_minutes": 45,
           "sleep_hours": 7.5,
           "resting_hr": 62
         }'
```

---

## 📱 3. Mobile PWA & Database Persistence

1. **PWA Mobile App Infrastructure:**
   - Manifest: `static/manifest.json` (`display: standalone`, `theme_color: #0a0f1d`).
   - Service Worker: `static/sw.js` for offline caching and instant launch.
   - Desktop & Mobile Navigation: "More" drawer sheet containing Canvas LMS, Gym Pro, Mind OS, and English Booster.
2. **Dual-Database Cloud Sync Engine:**
   - **Local Mode (SQLite):** Writes to `system_solo.db` (`canvas_completed_items`, `health_sync_logs`).
   - **Serverless Cloud Mode (Neon PostgreSQL):** Writes to `pg_canvas_completed_items`, `pg_health_logs`, and `pg_workout_log` on Vercel.

---

*Documentation auto-generated by Antigravity Engine v2.0.*
