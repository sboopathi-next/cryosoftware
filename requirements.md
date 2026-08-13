### gym pro is the one app in it /gympro is the excellent there we are tracking time right can you pleaes add button to record time and pause start save , manual time also i should able to do here.


### and mobile widget from sharedjs file there first is dashboard good , second is canvas good but third should be gympro which is in 4 . and 4 th should be mindos , other we can keep in more ---.


## need to track my work what i am doing in my office what i will send here using api my work should able to show in another module , store that in one db and show that in one visual, there i will log the work perfectly description i will give , mu post json will be . method will post, 
url = /api/work_tracker/log_work 
``` json
{
    'workItemId':'key (unique)',
    'description':'description of work',
    'workDate':'date of work',
    'Category': 'category of work',
    'hours' : 'how long i have spend on the work'
}
```
### for above work you need to generate xp in exponential way , will work on same category the calculation should increase exponentially 

### leetcode not only , manual sync need auto sync also , every refresh we do for dashboard . before that sync will be excellent now sync is updating as completed even i not complete also

###  without affecting functionality do this 

### bug meditation task not auto updating when meditation completed
### bug when mind os log is done , mind os task not updating automatically

This is a massive upgrade for **The System**. We are turning **GymPro** into an active real-time workout tracker and adding an **Office Work Tracker** with an exponential category mastery curve to reward deep focus and domain specialization.

Here is the complete implementation architecture to update your Windows background daemon and mobile interface.

---

## 1. GymPro Timer & Manual Logger Component

This updates your `/gympro` interface with a real-time Stopwatch (Start, Pause, Resume, Save) alongside a Manual Entry form so you can log workouts whether you track them live or input them after the session.

### Backend API Endpoint (`api/server.py`)

Add this endpoint to handle both live timer submissions and manual workout entries:

```python
import sqlite3
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI()
DB_PATH = "C:/antigravity_core/data/system_solo.db"

class GymLogPayload(BaseModel):
    duration_minutes: float
    workout_type: str  # e.g., "Weightlifting", "Cardio", "Push-Ups"
    is_manual: bool = False
    notes: Optional[str] = ""

@app.post("/api/gympro/log_workout")
def log_gym_session(data: GymLogPayload):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Base XP: 5 XP per 10 workout minutes
    base_xp = int((data.duration_minutes / 10.0) * 5)
    
    # Calculate Stat Boosts
    str_gain = int(data.duration_minutes / 10.0) * 2
    wil_gain = 5 if data.duration_minutes >= 30 else 2
    
    # Update Player Table
    cursor.execute("""
        UPDATE player 
        SET current_xp = current_xp + ?,
            str_stat = str_stat + ?,
            wil_stat = wil_stat + ?,
            cognitive_energy = MIN(100, cognitive_energy + 20)
        WHERE id = 1
    """, (base_xp, str_gain, wil_gain))
    
    # Log Workout History
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gym_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            duration_minutes REAL,
            workout_type TEXT,
            is_manual INTEGER,
            notes TEXT,
            xp_awarded INTEGER,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        INSERT INTO gym_logs (duration_minutes, workout_type, is_manual, notes, xp_awarded)
        VALUES (?, ?, ?, ?, ?)
    """, (data.duration_minutes, data.workout_type, 1 if data.is_manual else 0, data.notes, base_xp))
    
    conn.commit()
    conn.close()
    
    return {
        "status": "SUCCESS",
        "xp_earned": base_xp,
        "str_gained": str_gain,
        "wil_gained": wil_gain,
        "message": f"Gym Session Recorded! +{base_xp} XP | +{str_gain} STR"
    }

```

### Frontend Timer UI Component (`frontend/GymPro.jsx` / Web UI)

```javascript
import React, { useState, useEffect } from 'react';

export default function GymPro() {
  const [seconds, setSeconds] = useState(0);
  const [isActive, setIsActive] = useState(false);
  const [workoutType, setWorkoutType] = useState('Strength Training');
  const [manualMinutes, setManualMinutes] = useState('');

  useEffect(() => {
    let interval = null;
    if (isActive) {
      interval = setInterval(() => setSeconds(s => s + 1), 1000);
    } else {
      clearInterval(interval);
    }
    return () => clearInterval(interval);
  }, [isActive]);

  const formatTime = (totalSec) => {
    const mins = Math.floor(totalSec / 60).toString().padStart(2, '0');
    const secs = (totalSec % 60).toString().padStart(2, '0');
    return `${mins}:${secs}`;
  };

  const handleSaveTimer = async () => {
    const mins = Math.max(1, Math.round(seconds / 60));
    await sendGymPayload(mins, workoutType, false);
    setIsActive(false);
    setSeconds(0);
  };

  const handleSaveManual = async (e) => {
    e.preventDefault();
    if (!manualMinutes || manualMinutes <= 0) return;
    await sendGymPayload(parseFloat(manualMinutes), workoutType, true);
    setManualMinutes('');
  };

  const sendGymPayload = async (duration, type, isManual) => {
    const res = await fetch('/api/gympro/log_workout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ duration_minutes: duration, workout_type: type, is_manual: isManual })
    });
    const data = await res.json();
    alert(data.message);
  };

  return (
    <div className="p-6 bg-slate-900 text-white rounded-xl border border-slate-800">
      <h2 className="text-2xl font-bold text-cyan-400 mb-4">🏋️ GYM PRO CONTROL</h2>
      
      {/* REAL-TIME STOPWATCH */}
      <div className="bg-slate-800 p-6 rounded-lg text-center mb-6">
        <div className="text-5xl font-mono mb-4 text-cyan-300">{formatTime(seconds)}</div>
        <div className="flex justify-center gap-3">
          {!isActive ? (
            <button onClick={() => setIsActive(true)} className="bg-emerald-600 px-6 py-2 rounded-lg font-bold">Start</button>
          ) : (
            <button onClick={() => setIsActive(false)} className="bg-amber-600 px-6 py-2 rounded-lg font-bold">Pause</button>
          )}
          <button onClick={handleSaveTimer} className="bg-cyan-600 px-6 py-2 rounded-lg font-bold">Save Workout</button>
          <button onClick={() => { setIsActive(false); setSeconds(0); }} className="bg-rose-700 px-4 py-2 rounded-lg">Reset</button>
        </div>
      </div>

      {/* MANUAL WORKOUT LOG ENTRY */}
      <form onSubmit={handleSaveManual} className="bg-slate-800 p-4 rounded-lg flex flex-col gap-3">
        <h3 className="text-sm font-semibold text-slate-400">Manual Entry Override</h3>
        <div className="flex gap-3">
          <input 
            type="number" 
            placeholder="Duration (Minutes)" 
            value={manualMinutes} 
            onChange={(e) => setManualMinutes(e.target.value)}
            className="bg-slate-900 border border-slate-700 p-2 rounded w-full text-white"
          />
          <select 
            value={workoutType} 
            onChange={(e) => setWorkoutType(e.target.value)}
            className="bg-slate-900 border border-slate-700 p-2 rounded text-white"
          >
            <option>Strength Training</option>
            <option>Cardio / Running</option>
            <option>Calisthenics</option>
          </select>
          <button type="submit" className="bg-purple-600 px-4 py-2 rounded font-bold">Log Manual</button>
        </div>
      </form>
    </div>
  );
}

```

---

## 2. Mobile Navigation & Scriptable Widget Layout

To update your Scriptable JS (`mobile_widget.js`) navigation bar layout, order the screens as requested:

1. **Dashboard**
2. **Canvas**
3. **GymPro** (Moved from 4 to 3)
4. **MindOS** (Moved to 4)
5. **More (`---`)** $\rightarrow$ *(Syllabus, Tech Affairs, Human Journal, Stoic Log)*

### Scriptable Widget Configuration (`mobile_widget.js`)

```javascript
// ANTIGRAVITY MOBILE WIDGET - NAVIGATION CONFIG
const NAV_LAYOUT = [
  { id: "dashboard", label: "1. Dashboard", icon: "⚡" },
  { id: "canvas",    label: "2. Canvas LMS", icon: "🎓" },
  { id: "gympro",    label: "3. Gym Pro",    icon: "🏋️" },
  { id: "mindos",    label: "4. Mind OS",    icon: "🧠" },
  { id: "separator", label: "---",           icon: " " },
  { id: "more",      label: "More Modules",  icon: "📂" }
];

async function createWidget() {
  let widget = new ListWidget();
  widget.backgroundColor = new Color("#0f172a"); // Dark slate background

  // Fetch stats from local FastAPI endpoint
  let req = new Request("http://192.168.1.100:8000/api/dashboard");
  let data = await req.loadJSON();

  // Header Title
  let title = widget.addText("⚡ ANTIGRAVITY OS");
  title.textColor = new Color("#38bdf8");
  title.font = Font.boldSystemFont(14);

  widget.addSpacer(6);

  // Active Tab Highlight: Gym Pro (Tab 3)
  let activeTab = widget.addText(`Active: ${NAV_LAYOUT[2].icon} ${NAV_LAYOUT[2].label}`);
  activeTab.textColor = new Color("#22c55e");
  activeTab.font = Font.systemFont(12);

  // Level & XP Bar
  let statsText = widget.addText(`LVL ${data.level} | STR: ${data.attributes.STR} | AGI: ${data.attributes.AGI}`);
  statsText.textColor = new Color("#f8fafc");
  statsText.font = Font.monoSystemFont(11);

  return widget;
}

```

---

## 3. Office Work Tracker & Exponential XP Engine

This module logs your daily office work activities via API, stores them in SQLite, displays them visually on your dashboard, and calculates XP using an **Exponential Domain Mastery Curve**.

### SQLite Schema Addition (`engine/database.py`)

Run this SQL creation query during server initialization:

```sql
CREATE TABLE IF NOT EXISTS office_work_logs (
    workItemId TEXT PRIMARY KEY,
    description TEXT,
    workDate TEXT,
    category TEXT,
    hours REAL,
    xp_awarded REAL,
    category_streak INTEGER,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

```

### Backend API Ingestion Endpoint (`api/server.py`)

This handles your exact JSON POST payload format at `/api/work_tracker/log_work`:

```python
import math
import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
DB_PATH = "C:/antigravity_core/data/system_solo.db"

class WorkLogPayload(BaseModel):
    workItemId: str
    description: str
    workDate: str
    Category: str
    hours: float

def calculate_exponential_work_xp(category: str, hours: float, conn: sqlite3.Connection) -> tuple[float, int]:
    """
    Calculates XP exponentially based on category depth.
    Base Rate = 40 XP / hour.
    Exponential Growth Multiplier = 1 + 0.25 * (1.20 ^ category_count)
    """
    cursor = conn.cursor()
    
    # Get total previous logs in this same category
    cursor.execute("SELECT COUNT(*) FROM office_work_logs WHERE category = ?", (category,))
    category_count = cursor.fetchone()[0]
    
    base_xp_per_hour = 40.0
    
    # Exponential Multiplier Equation
    multiplier = 1.0 + (0.25 * math.pow(1.20, min(category_count, 15)))
    
    total_xp = round(hours * base_xp_per_hour * multiplier, 2)
    
    return total_xp, category_count + 1

@app.post("/api/work_tracker/log_work")
def log_office_work(payload: WorkLogPayload):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Prevent Duplicate WorkItemId Submission
    cursor.execute("SELECT workItemId FROM office_work_logs WHERE workItemId = ?", (payload.workItemId,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="workItemId already exists in database.")
    
    # 1. Calculate Exponential XP
    xp_earned, category_streak = calculate_exponential_work_xp(payload.Category, payload.hours, conn)
    
    # 2. Store Work Log
    cursor.execute("""
        INSERT INTO office_work_logs (workItemId, description, workDate, category, hours, xp_awarded, category_streak)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (payload.workItemId, payload.description, payload.workDate, payload.Category, payload.hours, xp_earned, category_streak))
    
    # 3. Update Player Profile Stats (Office Work levels up AGI & INT)
    agi_boost = int(payload.hours * 2)
    int_boost = int(payload.hours * 1)
    
    cursor.execute("""
        UPDATE player 
        SET current_xp = current_xp + ?,
            agi_stat = agi_stat + ?,
            int_stat = int_stat + ?
        WHERE id = 1
    """, (xp_earned, agi_boost, int_boost))
    
    conn.commit()
    conn.close()
    
    return {
        "status": "SUCCESS",
        "workItemId": payload.workItemId,
        "xp_awarded": xp_earned,
        "category": payload.Category,
        "category_streak": category_streak,
        "stat_boosts": {"AGI": f"+{agi_boost}", "INT": f"+{int_boost}"},
        "message": f"Work Logged! Category Depth Level: {category_streak} | Earned +{xp_earned} XP!"
    }

```

---

## 4. Antigravity System Feed: `WORK_TRACKER_XP.md`

Save this document as `C:\antigravity_core\docs\WORK_TRACKER_XP.md` to feed the exact mathematical specifications into your **Antigravity** core engine.

```markdown
# ANTIGRAVITY SYSTEM MODULE: EXPONENTIAL WORK TRACKER

## 1. System Philosophy
Task-switching between fragmented context domains reduces cognitive efficiency and triggers ego depletion. To encourage deep domain mastery in office work, the **Office Work Tracker Engine** rewards repeat activity within the same `Category` using an **Exponential Growth Curve**.

---

## 2. Mathematical XP Mechanics

For any incoming work log payload $L$ containing hours $H$ and Category $C$:

$$\text{XP}_{\text{awarded}} = H \times B \times \left(1 + \gamma \cdot (1 + \beta)^{\min(N_{C}, 15)}\right)$$

Where:
* $H$: Total duration spent on the work item in hours (`hours`).
* $B$: Base XP rate constant ($B = 40.0\text{ XP/hour}$).
* $N_C$: Cumulative count of logged work items within category $C$ (`category_streak`).
* $\gamma$: Base exponential scaling factor ($\gamma = 0.25$).
* $\beta$: Exponential rate coefficient ($\beta = 0.20$, representing a 20% compounding yield per category repetition).

---

## 3. Exponential Growth Yield Table

| Category Logs ($N_C$) | Mastery Multiplier | Base Rate ($40\text{ XP/hr}$) | Yield per 2-Hour Task |
| :---: | :---: | :---: | :---: |
| **0** (New Category) | $1.25\times$ | $50.0\text{ XP/hr}$ | **100.0 XP** |
| **1** | $1.30\times$ | $52.0\text{ XP/hr}$ | **104.0 XP** |
| **3** | $1.43\times$ | $57.2\text{ XP/hr}$ | **114.4 XP** |
| **5** | $1.62\times$ | $64.8\text{ XP/hr}$ | **129.6 XP** |
| **10** (Deep Mastery) | $2.55\times$ | $102.0\text{ XP/hr}$ | **204.0 XP** |
| **15+** (Domain Specialist) | $4.85\times$ | $194.0\text{ XP/hr}$ | **388.0 XP!** |

---

## 4. Stat Attribute Distributing Map
Every logged work item dynamically scales the player's core attributes based on duration:

* **Agility ($\text{AGI}$):** $+2 \text{ points per hour}$ (Represents execution speed and system production delivery).
* **Intelligence ($\text{INT}$):** $+1 \text{ point per hour}$ (Represents domain knowledge retention).

---

## 5. API Interface Specification
* **Endpoint:** `POST /api/work_tracker/log_work`
* **Content-Type:** `application/json`

```json
{
  "workItemId": "JIRA-8921",
  "description": "Implemented NetSuite OAuth1 Token-Based Authentication integration pipeline in Python.",
  "workDate": "2026-08-14",
  "Category": "API Integration",
  "hours": 3.5
}

```

```

---

## 5. Office Work Visual UI Component (`frontend/WorkTrackerDashboard.jsx`)

Add this visual component to your main Web UI dashboard to display your logged office tasks, category distribution, and active mastery multipliers:

```javascript
import React, { useEffect, useState } from 'react';

export default function WorkTrackerDashboard() {
  const [logs, setLogs] = useState([]);
  const [categoryStats, setCategoryStats] = useState({});

  useEffect(() => {
    fetch('/api/work_tracker/logs')
      .then(res => res.json())
      .then(data => {
        setLogs(data.logs || []);
        setCategoryStats(data.category_summary || {});
      });
  }, []);

  return (
    <div className="p-6 bg-slate-900 text-white rounded-xl border border-slate-800">
      <h2 className="text-2xl font-bold text-indigo-400 mb-6">💼 OFFICE WORK MASTERY TRACKER</h2>
      
      {/* CATEGORY MULTIPLIER BADGES */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {Object.entries(categoryStats).map(([cat, stats]) => (
          <div key={cat} className="bg-slate-800 p-4 rounded-lg border border-indigo-900">
            <div className="text-xs text-indigo-300 font-semibold uppercase">{cat}</div>
            <div className="text-2xl font-bold">{stats.total_hours} hrs</div>
            <div className="text-xs text-emerald-400 mt-1">
              ⚡ {stats.multiplier}x Exponential XP Yield
            </div>
          </div>
        ))}
      </div>

      {/* WORK LOGS TABLE */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 text-sm">
              <th className="py-2">KEY</th>
              <th className="py-2">CATEGORY</th>
              <th className="py-2">DESCRIPTION</th>
              <th className="py-2">HOURS</th>
              <th className="py-2">XP EARNED</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 text-sm">
            {logs.map((log) => (
              <tr key={log.workItemId} className="hover:bg-slate-800/50">
                <td className="py-3 font-mono text-indigo-400">{log.workItemId}</td>
                <td className="py-3 font-semibold">{log.category}</td>
                <td className="py-3 text-slate-300 max-w-xs truncate">{log.description}</td>
                <td className="py-3 font-bold">{log.hours}h</td>
                <td className="py-3 text-emerald-400 font-mono">+{log.xp_awarded} XP</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

```