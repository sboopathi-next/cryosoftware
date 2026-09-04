import sys
import os
import re
import json
import math
import time
import requests
from datetime import datetime, date

# Ensure parent directory is in sys.path
pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if pkg_root not in sys.path:
    sys.path.insert(0, pkg_root)

from engine.database import get_db_connection, get_state, save_state, add_xp, log_activity_file, log_task_completion, _DB_WRITE_LOCK

# Curated catalog of IELTS Part 2 & Part 3 Topics with PREP Framework Guidance
IELTS_TOPICS = [
    {
        "id": "ielts_p2_ai_system",
        "type": "IELTS_PART_2",
        "category": "Technology & Innovation",
        "title": "Describe a breakthrough software system or AI architecture that optimized human workflows.",
        "target_band": 8.5,
        "cues": [
            "What underlying technology or algorithmic paradigm it utilizes",
            "How it orchestrates streaming data and high-dimensional memory",
            "Why you consider this system transformative for human intellect"
        ],
        "prep_framework": {
            "point": "Without hesitation, I would highlight autonomous multimodal RAG frameworks for cognitive research.",
            "reason": "The imperative justification lies in bypassing volatile human memory limits during deep domain synthesis.",
            "example": "For instance, synthesizing 80 medical patents in 40 seconds with zero hallucination rate.",
            "point_recap": "Consequently, this represents an indispensable intellectual exoskeleton rather than simple automation."
        }
    },
    {
        "id": "ielts_p2_leadership",
        "type": "IELTS_PART_2",
        "category": "Leadership & Strategy",
        "title": "Describe a difficult crisis where strategic decision-making prevented systemic failure.",
        "target_band": 8.5,
        "cues": [
            "What the nature of the high-stakes conflict or bottleneck was",
            "What actions and analytical methodologies were deployed",
            "What long-term resilience or structural lessons were mastered"
        ],
        "prep_framework": {
            "point": "I would articulate a high-consequence system blackout during peak production data migration.",
            "reason": "Immediate triage required isolating failure domain boundaries without corrupting transactional integrity.",
            "example": "Specifically, executing circuit-breaker failovers within 12 seconds saved critical downstream data.",
            "point_recap": "Thus, calm analytical execution under extreme pressure is the hallmark of true engineering leadership."
        }
    },
    {
        "id": "ielts_p3_automation_ethics",
        "type": "IELTS_PART_3",
        "category": "Abstract Discussion",
        "title": "To what extent will fully autonomous AI systems alter human cognitive autonomy in the next decade?",
        "target_band": 9.0,
        "cues": [
            "Address cognitive atrophy versus intellectual amplification",
            "Discuss algorithmic alignment, accountability, and deterministic bounds",
            "Synthesize your philosophical stance on human-AI co-evolution"
        ],
        "prep_framework": {
            "point": "Autonomous AI will fundamentally shift human cognition from manual execution to high-level governance.",
            "reason": "Delegating routine procedural computation unleashes human focus for creative synthesis and ethics.",
            "example": "Look at modern software developers who leverage AI copilot tools to build architectures 10x faster.",
            "point_recap": "Therefore, cognitive autonomy will expand provided humans maintain rigorous critical oversight."
        }
    }
]

FILLER_WORDS = ["um", "uh", "like", "actually", "basically", "you know", "i mean", "sort of", "kind of", "literally"]

class IeltsSpeakingEngine:
    def __init__(self, ollama_url="http://localhost:11434/api/generate", model="llama3:8b"):
        self.ollama_url = ollama_url
        self.model = model

    def get_topics(self):
        return IELTS_TOPICS

    def compute_telemetry(self, transcript: str, duration_seconds: float):
        clean_text = re.sub(r'[^\w\s]', '', transcript.lower())
        words = clean_text.split()
        word_count = len(words)
        
        duration_mins = max(0.1, duration_seconds / 60.0)
        wpm = round(word_count / duration_mins, 1)

        # Pacing analysis
        if wpm < 105:
            pacing_status = "HESITANT"
            pacing_critique = "Pacing is hesitant (<105 WPM). Focus on speech continuity and reducing hesitation delays."
        elif wpm > 170:
            pacing_status = "RUSHED"
            pacing_critique = "Pacing is rushed (>170 WPM). Articulate vowels clearly and control your breathing cadence."
        else:
            pacing_status = "OPTIMAL"
            pacing_critique = "Cadence is optimal (125-150 WPM). Natural rhythm and articulation sustained."

        # Filler Word Sentinel
        filler_matches = []
        for w in words:
            if w in FILLER_WORDS:
                filler_matches.append(w)
        
        # Check phrase fillers like "you know", "i mean", "sort of", "kind of"
        phrase_text = " " + " ".join(words) + " "
        for phrase in ["you know", "i mean", "sort of", "kind of"]:
            cnt = len(re.findall(rf'\b{phrase}\b', phrase_text))
            if cnt > 0:
                filler_matches.extend([phrase] * cnt)

        filler_count = len(filler_matches)
        filler_ratio = round((filler_count / max(1, word_count)) * 100, 1)

        # Type-Token Ratio (Vocabulary Richness)
        unique_words = set(words)
        ttr = round(len(unique_words) / max(1, word_count), 2)

        return {
            "word_count": word_count,
            "duration_seconds": round(duration_seconds, 1),
            "wpm": wpm,
            "pacing_status": pacing_status,
            "pacing_critique": pacing_critique,
            "filler_count": filler_count,
            "filler_ratio": filler_ratio,
            "filler_words_detected": list(set(filler_matches)),
            "ttr": ttr
        }

    def evaluate_with_local_llm(self, topic: str, transcript: str, telemetry: dict):
        """
        Attempts evaluation via local Ollama LLM. Falls back to deterministic rule-based evaluation if unavailable.
        """
        prompt = f"""You are a senior Cambridge certified IELTS Speaking Examiner. Evaluate the following candidate speech.

Topic: {topic}
Transcript: "{transcript}"
Telemetry: Words={telemetry['word_count']}, WPM={telemetry['wpm']}, Filler Count={telemetry['filler_count']}, Filler Ratio={telemetry['filler_ratio']}%, TTR={telemetry['ttr']}

Evaluate strict IELTS Speaking Band (0.0 to 9.0) across 4 criteria:
1. Fluency & Coherence (FC)
2. Lexical Resource (LR)
3. Grammatical Range & Accuracy (GRA)
4. Pronunciation & Enunciation (P)

Respond ONLY with a valid raw JSON object formatted exactly as below (no extra prose or markdown wrappers):
{{
  "overall_band": 7.5,
  "fc_score": 7.5,
  "lr_score": 8.0,
  "gra_score": 7.0,
  "prep_compliance": true,
  "coaching_critique": "Strong coherent delivery with advanced collocations. Control minor sentence structural resets.",
  "lexical_upgrades": [
    {{"original": "did things very fast", "advanced": "expedited execution with high velocity", "reason": "Precision vocabulary for technical speed"}},
    {{"original": "big problem", "advanced": "formidable systemic bottleneck", "reason": "Band 8.5 formal noun phrase"}}
  ]
}}
"""
        try:
            res = requests.post(
                self.ollama_url,
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=12
            )
            if res.status_code == 200:
                raw_out = res.json().get("response", "").strip()
                # Clean code blocks if present
                clean_json = re.sub(r'^```json\s*|\s*```$', '', raw_out, flags=re.MULTILINE).strip()
                data = json.loads(clean_json)
                return data
        except Exception as e:
            print(f"[IELTS Engine Note] Ollama API offline or timed out ({e}). Using local heuristic evaluation engine.")

        # Deterministic Algorithmic Fallback Scoring
        wpm = telemetry['wpm']
        word_count = telemetry['word_count']
        filler_ratio = telemetry['filler_ratio']
        ttr = telemetry['ttr']

        # FC Score
        if 120 <= wpm <= 160 and filler_ratio <= 2.0:
            fc = 8.0
        elif 105 <= wpm <= 170 and filler_ratio <= 4.0:
            fc = 7.0
        elif wpm < 100 or filler_ratio > 5.0:
            fc = 6.0
        else:
            fc = 6.5

        # LR Score
        if ttr >= 0.55 and word_count >= 80:
            lr = 8.0
        elif ttr >= 0.45:
            lr = 7.5
        else:
            lr = 6.5

        # GRA Score
        gra = 7.5 if word_count >= 100 else (7.0 if word_count >= 50 else 6.0)

        overall = round((fc + lr + gra) / 3.0, 1)

        return {
            "overall_band": overall,
            "fc_score": fc,
            "lr_score": lr,
            "gra_score": gra,
            "prep_compliance": word_count >= 60,
            "coaching_critique": f"Solid delivery ({telemetry['wpm']} WPM). Vocabulary richness TTR is {ttr}. Minimizing filler words will push Fluency to Band 8.5+.",
            "lexical_upgrades": [
                {"original": "very fast", "advanced": "with remarkable velocity", "reason": "C1 Academic Intensity"},
                {"original": "big problem", "advanced": "systemic vulnerability", "reason": "Band 8+ Lexical Precision"}
            ]
        }

    def process_speaking_session(self, topic: str, transcript: str, duration_seconds: float, test_type: str = "IELTS_PART_2"):
        telemetry = self.compute_telemetry(transcript, duration_seconds)
        eval_res = self.evaluate_with_local_llm(topic, transcript, telemetry)

        overall_band = eval_res.get("overall_band", 7.0)
        fc_score = eval_res.get("fc_score", 7.0)
        lr_score = eval_res.get("lr_score", 7.0)
        gra_score = eval_res.get("gra_score", 7.0)
        coaching_critique = eval_res.get("coaching_critique", "")

        # Gamification Calculation
        base_xp = 60
        band_bonus = 30 if overall_band >= 7.5 else 0
        zero_filler_bonus = 20 if telemetry["filler_count"] == 0 else 0
        total_xp = base_xp + band_bonus + zero_filler_bonus

        # Database Commit
        with _DB_WRITE_LOCK:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO ielts_speaking_logs (
                test_type, topic, duration_seconds, word_count, words_per_minute,
                filler_count, estimated_band, fc_score, lr_score, gra_score,
                transcript, ai_feedback, xp_awarded
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                test_type, topic, telemetry["duration_seconds"], telemetry["word_count"], telemetry["wpm"],
                telemetry["filler_count"], overall_band, fc_score, lr_score, gra_score,
                transcript, json.dumps(eval_res), total_xp
            ))
            conn.commit()
            conn.close()

        # Update System State & Attributes
        state = get_state() or {}
        prev_completed = bool(state.get("english_completed", 0))

        state["english_completed"] = 1
        state["agi"] = state.get("agi", 10) + 3
        state["int"] = state.get("int", 10) + (2 if band_bonus else 1)
        state["wil"] = state.get("wil", 10) + 3
        state["energy"] = max(0.0, state.get("energy", 100.0) - 8.0) # -8.0 E Drain

        save_state(state)
        add_xp(total_xp)

        if not prev_completed:
            try:
                log_task_completion("english")
            except Exception:
                pass

        log_activity_file(
            doing=f"Completed IELTS Speaking Sprint ({overall_band} Band)",
            accomplished=f"Spoke {telemetry['word_count']} words in {telemetry['duration_seconds']}s ({telemetry['wpm']} WPM). Overall Band: {overall_band}. +{total_xp} XP, +3 AGI, +2 INT, +3 WIL."
        )

        return {
            "status": "SUCCESS",
            "overall_band": overall_band,
            "fc_score": fc_score,
            "lr_score": lr_score,
            "gra_score": gra_score,
            "telemetry": telemetry,
            "ai_evaluation": eval_res,
            "xp_awarded": total_xp,
            "attributes_gained": {"AGI": 3, "INT": 2 if band_bonus else 1, "WIL": 3},
            "energy_drained": 8.0
        }

    def get_phrase_vault(self):
        conn = get_db_connection()
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM phrase_vault ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        return rows

    def add_phrase_to_vault(self, phrase: str, meaning_context: str = "", tamil_equivalent: str = "", source: str = "Cinema / Dialogue"):
        phrase = phrase.strip()
        if not phrase:
            return {"status": "error", "message": "Phrase cannot be empty."}
        with _DB_WRITE_LOCK:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO phrase_vault (phrase, meaning_context, tamil_equivalent, source)
            VALUES (?, ?, ?, ?)
            """, (phrase, meaning_context.strip(), tamil_equivalent.strip(), source.strip()))
            conn.commit()
            conn.close()
        return {"status": "SUCCESS", "message": f"Added phrase '{phrase}' to phrase vault!"}

    def get_logs_history(self, limit: int = 20):
        conn = get_db_connection()
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ielts_speaking_logs ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows
