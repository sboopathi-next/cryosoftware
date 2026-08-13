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

## 4. Stat Attribute Distribution Map
Every logged work item dynamically scales the player's core attributes based on duration:

* **Agility ($\text{AGI}$):** $+2 \text{ points per hour}$ (Represents execution speed and system production delivery).
* **Intelligence ($\text{INT}$):** $+1 \text{ point per hour}$ (Represents domain knowledge retention).

---

## 5. API Interface Specification
* **Endpoint:** `POST /api/work_tracker/log_work`
* **Content-Type:** `application/json`
* **Multi-Session Support:** Every POST creates a new log entry identified by `workLogId`. A single `workItemId` (e.g. `JIRA-8921`) can be logged multiple times over different dates/sessions as work progresses.

### Request Payload
```json
{
  "workItemId": "JIRA-8921",
  "description": "Implemented NetSuite OAuth1 Token-Based Authentication integration pipeline in Python.",
  "workDate": "2026-08-14",
  "Category": "API Integration",
  "hours": 3.5
}
```

### Response Payload
```json
{
  "status": "SUCCESS",
  "workLogId": 42,
  "workItemId": "JIRA-8921",
  "xp_awarded": 182.0,
  "category": "API Integration",
  "category_streak": 4,
  "stat_boosts": { "AGI": "+7", "INT": "+3" },
  "message": "Work Logged! Category Depth Level: 4 | Log #42 | Earned +182.0 XP!"
}
```
