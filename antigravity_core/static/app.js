// ═══════════════════════════════════════════════════════════════════
//  ANTIGRAVITY CORE — Frontend App Engine v2.0
//  GATE 2028 Mission Control · ML Engineer Track
// ═══════════════════════════════════════════════════════════════════

// ─── SVG GRADIENT DEFS (inject for ring animations) ─────────────────────────
document.body.insertAdjacentHTML('afterbegin', `
<svg class="ring-gradient-defs" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="ringGradient" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#6366f1"/>
      <stop offset="100%" style="stop-color:#3b82f6"/>
    </linearGradient>
    <linearGradient id="energyGradientHigh" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#10b981"/>
      <stop offset="100%" style="stop-color:#047857"/>
    </linearGradient>
    <linearGradient id="energyGradientMid" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#f59e0b"/>
      <stop offset="100%" style="stop-color:#b45309"/>
    </linearGradient>
    <linearGradient id="energyGradientLow" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#ef4444"/>
      <stop offset="100%" style="stop-color:#b91c1c"/>
    </linearGradient>
  </defs>
</svg>`);

// ─── STATE ─────────────────────────────────────────────────────────────────
let currentStats = {};
let fullSyllabus = {};
let workoutOptions = {};   // { Category: [workouts...] }
let setCount = 0;
let currentSyllabusPage = 0;
const WEEKS_PER_PAGE = 4;  // Show 4 weeks per page
const GATE_COURSE_COLORS = {
    Python_Data_Science: '#3b82f6',
    Linear_Algebra: '#8b5cf6',
    Probability_Stats: '#ec4899',
    Statistical_Inference: '#f59e0b',
    EDA: '#10b981',
    Database_Systems: '#6366f1',
    Data_Mining_Forecasting: '#14b8a6',
    Advanced_Forecasting: '#f97316',
    DSA_LeetCode: '#ef4444',
    AI_Agents: '#a855f7',
    Machine_Learning: '#06b6d4'
};

// ─── TAB SWITCHING ─────────────────────────────────────────────────────────
function switchTab(tabId) {
    document.querySelectorAll('.tab-panel').forEach(p => {
        p.classList.add('hidden');
        p.classList.remove('active');
    });
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    const panel = document.getElementById(`tab-${tabId}`);
    const navItem = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
    if (panel) { panel.classList.remove('hidden'); panel.classList.add('active'); }
    if (navItem) navItem.classList.add('active');

    // Lazy-load data on tab switch
    if (tabId === 'syllabus' && Object.keys(fullSyllabus).length === 0) fetchSyllabus();
    if (tabId === 'gym') { loadGymOptions(); fetchWorkoutHistory(); }
    if (tabId === 'logs') fetchLogs();
}

// ─── SETTINGS MODAL (API KEY) ──────────────────────────────────────────────
function openSettingsModal() {
    const existing = localStorage.getItem('gemini_api_key') || '';
    document.getElementById('gemini-api-key-input').value = existing;
    document.getElementById('settings-modal').classList.remove('hidden');
}
function closeSettingsModal() {
    document.getElementById('settings-modal').classList.add('hidden');
}
function saveApiKey() {
    const key = document.getElementById('gemini-api-key-input').value.trim();
    localStorage.setItem('gemini_api_key', key);
    closeSettingsModal();
    showToast('API Key saved!', 'success');
}
document.getElementById('settings-modal').addEventListener('click', function(e) {
    if (e.target === this) closeSettingsModal();
});

// ─── FETCH STATS ────────────────────────────────────────────────────────────
async function fetchStatus() {
    try {
        const res = await fetch('/stats');
        if (!res.ok) throw new Error('Failed to fetch stats');
        const data = await res.json();
        currentStats = data;
        renderStatus(data);
    } catch (err) {
        console.error('Error loading stats:', err);
    }
}

function renderStatus(data) {
    // Level ring
    const lvlEl = document.getElementById('stat-level');
    if (lvlEl) lvlEl.innerText = data.level;

    const xpPercent = Math.min(100, (data.xp / data.xp_required) * 100);
    const ringCirc = 2 * Math.PI * 60; // r=60 → 376.99
    const ringOffset = ringCirc - (xpPercent / 100) * ringCirc;
    const ring = document.getElementById('xp-progress-ring');
    if (ring) { ring.style.strokeDasharray = ringCirc; ring.style.strokeDashoffset = ringOffset; }

    const xpBar = document.getElementById('xp-progress-bar');
    if (xpBar) xpBar.style.width = `${xpPercent}%`;

    const xpText = document.getElementById('xp-text');
    if (xpText) xpText.innerText = `XP: ${data.xp} / ${data.xp_required} (${Math.round(xpPercent)}%)`;

    const streakEl = document.getElementById('streak-days');
    if (streakEl) streakEl.innerText = data.streak_days || 0;

    // Energy ring
    const energy = data.energy;
    const ePct = document.getElementById('energy-percentage');
    if (ePct) {
        ePct.innerText = `${Math.round(energy)}%`;
        ePct.style.color = energy > 50 ? '#10b981' : energy > 20 ? '#f59e0b' : '#ef4444';
    }
    const energyCirc = 2 * Math.PI * 40; // r=40 → 251.33
    const energyOffset = energyCirc - (energy / 100) * energyCirc;
    const eRing = document.getElementById('energy-ring-bar');
    if (eRing) {
        eRing.style.strokeDasharray = energyCirc;
        eRing.style.strokeDashoffset = energyOffset;
        eRing.style.stroke = energy > 50 ? '#10b981' : energy > 20 ? '#f59e0b' : '#ef4444';
    }
    const eIcon = document.querySelector('.energy-center-icon i');
    if (eIcon) {
        eIcon.style.color = energy > 50 ? '#10b981' : energy > 20 ? '#f59e0b' : '#ef4444';
    }

    // Circuit breaker
    const cAlert = document.getElementById('circuit-breaker-alert');
    if (cAlert) { data.lockout_active ? cAlert.classList.remove('hidden') : cAlert.classList.add('hidden'); }

    // Attributes
    const attrs = data.attributes || {};
    const setAttr = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
    setAttr('attr-str', attrs.STR);
    setAttr('attr-int', attrs.INT);
    setAttr('attr-agi', attrs.AGI);
    setAttr('attr-wil', attrs.WIL);
    setAttr('attr-hrt', attrs.HRT);
    setAttr('attr-stc', attrs.STC);

    // Active quest
    const q = document.getElementById('target-quest');
    if (q) q.innerText = data.active_quest;

    // Course selector sync
    const cs = document.getElementById('course-selector');
    if (cs && data.active_subject && cs.value !== data.active_subject) {
        cs.value = data.active_subject;
    }
}

// ─── FETCH SYLLABUS ────────────────────────────────────────────────────────
async function fetchSyllabus() {
    try {
        const res = await fetch('/api/syllabus');
        if (!res.ok) throw new Error('Failed to fetch syllabus');
        fullSyllabus = await res.json();
        renderSyllabusForActiveCourse();
        renderGATEProgressBars();
    } catch (err) {
        console.error('Error loading syllabus:', err);
    }
}

function renderSyllabusForActiveCourse() {
    const cs = document.getElementById('course-selector');
    const selectedCourseId = cs ? cs.value : 'Python_Data_Science';
    const course = fullSyllabus.courses && fullSyllabus.courses[selectedCourseId];
    if (!course) return;

    const weeks = course.weeks || [];
    const totalPages = Math.ceil(weeks.length / WEEKS_PER_PAGE);

    // Clamp page
    if (currentSyllabusPage >= totalPages) currentSyllabusPage = Math.max(0, totalPages - 1);

    // Calc progress
    let totalItems = 0, completedItems = 0;
    weeks.forEach(w => w.items.forEach(item => {
        totalItems++;
        if (item.completed) completedItems++;
    }));

    const pLabel = document.getElementById('course-progress-label');
    if (pLabel) pLabel.innerText = `${completedItems} / ${totalItems} Completed`;
    const pct = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0;
    const pPct = document.getElementById('course-percentage');
    if (pPct) pPct.innerText = `${pct}%`;
    const pBar = document.getElementById('course-progress-bar');
    if (pBar) pBar.style.width = `${pct}%`;

    // Page dots
    const dotsEl = document.getElementById('page-indicators');
    if (dotsEl) {
        dotsEl.innerHTML = '';
        for (let i = 0; i < totalPages; i++) {
            const dot = document.createElement('div');
            dot.className = `page-dot ${i === currentSyllabusPage ? 'active' : ''}`;
            dot.onclick = () => { currentSyllabusPage = i; renderSyllabusForActiveCourse(); };
            dotsEl.appendChild(dot);
        }
    }

    // Page label
    const botLabel = document.getElementById('page-label-bottom');
    if (botLabel) botLabel.innerText = `Page ${currentSyllabusPage + 1} of ${totalPages}`;

    // Prev/Next buttons
    const btnPrev = document.getElementById('btn-prev-page');
    const btnNext = document.getElementById('btn-next-page');
    if (btnPrev) btnPrev.disabled = currentSyllabusPage === 0;
    if (btnNext) btnNext.disabled = currentSyllabusPage >= totalPages - 1;

    // Render current page of weeks
    const container = document.getElementById('syllabus-lectures');
    if (!container) return;
    container.innerHTML = '';

    const pageWeeks = weeks.slice(
        currentSyllabusPage * WEEKS_PER_PAGE,
        (currentSyllabusPage + 1) * WEEKS_PER_PAGE
    );

    pageWeeks.forEach(week => {
        const weekGroup = document.createElement('div');
        weekGroup.className = 'week-group';

        const weekTitle = document.createElement('div');
        weekTitle.className = 'week-title';
        weekTitle.innerText = `Week ${week.week}: ${week.title}`;
        weekGroup.appendChild(weekTitle);

        week.items.forEach(item => {
            const lec = document.createElement('div');
            lec.className = `lecture-item ${item.completed ? 'completed' : ''}`;
            lec.innerHTML = `
                <div class="lecture-check" onclick="toggleLecture('${selectedCourseId}', '${item.id}', ${!item.completed})">
                    <i class="fa-solid fa-check"></i>
                </div>
                <div class="lecture-info">
                    <div class="lecture-name">${item.name}</div>
                    <div class="lecture-metadata">
                        <span class="lecture-badge req-lvl"><i class="fa-solid fa-lock" style="font-size:0.55rem"></i> Lvl ${item.level || 1}</span>
                        <span class="lecture-badge xp-val"><i class="fa-solid fa-star" style="font-size:0.55rem"></i> +${item.xp} XP</span>
                        ${item.completed_at ? `<span class="lecture-badge">✓ ${item.completed_at.split('T')[0]}</span>` : ''}
                    </div>
                </div>`;
            weekGroup.appendChild(lec);
        });

        container.appendChild(weekGroup);
    });
}

function prevSyllabusPage() {
    if (currentSyllabusPage > 0) { currentSyllabusPage--; renderSyllabusForActiveCourse(); window.scrollTo(0,0); }
}
function nextSyllabusPage() {
    const cs = document.getElementById('course-selector');
    const selectedCourseId = cs ? cs.value : 'Python_Data_Science';
    const course = fullSyllabus.courses && fullSyllabus.courses[selectedCourseId];
    if (!course) return;
    const totalPages = Math.ceil((course.weeks || []).length / WEEKS_PER_PAGE);
    if (currentSyllabusPage < totalPages - 1) { currentSyllabusPage++; renderSyllabusForActiveCourse(); window.scrollTo(0,0); }
}

// ─── TOGGLE LECTURE COMPLETION ─────────────────────────────────────────────
async function toggleLecture(subjectId, itemId, completed) {
    try {
        const res = await fetch('/api/syllabus/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ subject_id: subjectId, item_id: itemId, completed })
        });
        if (!res.ok) {
            const err = await res.json();
            showToast(`Error: ${err.detail}`, 'error');
            return;
        }
        await fetchStatus();
        await fetchSyllabus();
        showToast(completed ? '✓ Lecture completed! +XP gained' : 'Lecture unmarked', completed ? 'success' : 'info');
    } catch (err) {
        console.error('Error toggling lecture:', err);
    }
}

// ─── COURSE SELECTOR CHANGE ────────────────────────────────────────────────
const courseSelector = document.getElementById('course-selector');
if (courseSelector) {
    courseSelector.addEventListener('change', async () => {
        const subjectId = courseSelector.value;
        currentSyllabusPage = 0;
        try {
            await fetch('/api/syllabus/active', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ subject_id: subjectId })
            });
            await fetchStatus();
            renderSyllabusForActiveCourse();
        } catch (err) { console.error('Error setting active course:', err); }
    });
}

// ─── GATE PROGRESS BARS ─────────────────────────────────────────────────────
function renderGATEProgressBars() {
    const container = document.getElementById('gate-progress-bars');
    if (!container || !fullSyllabus.courses) return;
    container.innerHTML = '';

    const courseNames = {
        Python_Data_Science: 'Python Programming',
        Linear_Algebra: 'Linear Algebra',
        Probability_Stats: 'Probability & Stats',
        Statistical_Inference: 'Statistical Inference',
        EDA: 'Exploratory Data Analysis',
        Database_Systems: 'Database Systems',
        Data_Mining_Forecasting: 'Data Mining',
        Advanced_Forecasting: 'Advanced Forecasting',
        DSA_LeetCode: 'DSA & LeetCode',
        AI_Agents: 'AI & Agents',
        Machine_Learning: 'Machine Learning'
    };

    Object.entries(fullSyllabus.courses).forEach(([courseId, course]) => {
        let total = 0, completed = 0;
        (course.weeks || []).forEach(w => w.items.forEach(item => {
            total++; if (item.completed) completed++;
        }));
        const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
        const color = GATE_COURSE_COLORS[courseId] || '#6366f1';

        const row = document.createElement('div');
        row.className = 'gate-bar-row';
        row.innerHTML = `
            <div class="gate-bar-label" title="${courseNames[courseId] || courseId}">${courseNames[courseId] || courseId}</div>
            <div class="gate-bar-track">
                <div class="gate-bar-fill" style="width:${pct}%;background:${color}"></div>
            </div>
            <div class="gate-bar-pct">${completed}/${total}</div>`;
        container.appendChild(row);
    });
}

// ─── ACTIVITY LOGS ──────────────────────────────────────────────────────────
async function fetchLogs() {
    try {
        const res = await fetch('/api/activity_logs');
        if (!res.ok) throw new Error('Failed to fetch logs');
        renderLogs(await res.json());
    } catch (err) { console.error('Error loading logs:', err); }
}

function renderLogs(logs) {
    const container = document.getElementById('logs-list');
    if (!container) return;
    container.innerHTML = '';

    if (!logs.length) {
        container.innerHTML = `<div class="empty-state"><i class="fa-solid fa-clock" style="font-size:2rem;color:var(--text-muted);display:block;margin-bottom:0.5rem"></i>No check-in entries yet. Entries auto-spawn every 3 hours.</div>`;
        return;
    }

    logs.forEach(log => {
        const item = document.createElement('div');
        item.className = 'log-item';
        item.innerHTML = `
            <div class="log-marker"><i class="fa-solid fa-clock"></i></div>
            <div>
                <div class="log-time">${log.timestamp}</div>
                <div class="log-details">
                    <span><strong>Current:</strong> ${log.doing}</span>
                    <span><strong>Accomplished:</strong> ${log.did}</span>
                </div>
            </div>`;
        container.appendChild(item);
    });
}

async function triggerCheckin() {
    const btn = document.getElementById('btn-manual-checkin-logs');
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Opening...'; }
    try {
        const res = await fetch('/api/trigger_checkin', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') { showToast('Check-in logged!', 'success'); fetchLogs(); }
    } catch (err) { console.error('Error triggering check-in:', err); }
    finally {
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-clock-rotate-left"></i> Check-In Now'; }
    }
}

// ─── GYM CHECK ──────────────────────────────────────────────────────────────
async function markGymComplete() {
    try {
        const res = await fetch('/gym_check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ completed: true })
        });
        const data = await res.json();
        showToast(data.message, 'success');
        fetchStatus();
    } catch (err) { console.error('Gym check error:', err); }
}

// ─── GYM TRACKER ────────────────────────────────────────────────────────────
async function loadGymOptions() {
    try {
        const res = await fetch('/api/workouts/options');
        if (!res.ok) throw new Error('Failed to load options');
        const data = await res.json();
        workoutOptions = data.categories || {};

        const catSelect = document.getElementById('wk-category');
        if (!catSelect) return;
        catSelect.innerHTML = '<option value="">-- Select Category --</option>';
        Object.keys(workoutOptions).sort().forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat; opt.textContent = cat;
            catSelect.appendChild(opt);
        });
    } catch (err) { console.error('Error loading gym options:', err); }
}

function loadWorkoutsForCategory() {
    const cat = document.getElementById('wk-category').value;
    const workoutSelect = document.getElementById('wk-exercise');
    workoutSelect.innerHTML = '<option value="">-- Select Exercise --</option>';
    if (!cat || !workoutOptions[cat]) return;
    workoutOptions[cat].forEach(w => {
        const opt = document.createElement('option');
        opt.value = w; opt.textContent = w;
        workoutSelect.appendChild(opt);
    });
}

function toggleCustomWorkoutForm() {
    const form = document.getElementById('custom-workout-form');
    if (form) form.classList.toggle('hidden');
}

async function addCustomWorkout() {
    const cat = document.getElementById('custom-category').value.trim();
    const exercise = document.getElementById('custom-exercise').value.trim();
    if (!cat || !exercise) { showToast('Please fill both fields.', 'error'); return; }

    try {
        const res = await fetch('/api/workouts/custom', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category: cat, workout: exercise })
        });
        const data = await res.json();
        showToast(data.message, data.status === 'success' ? 'success' : 'info');
        document.getElementById('custom-category').value = '';
        document.getElementById('custom-exercise').value = '';
        document.getElementById('custom-workout-form').classList.add('hidden');
        await loadGymOptions();
    } catch (err) { showToast('Error saving custom workout.', 'error'); }
}

// ─── SETS MANAGEMENT ────────────────────────────────────────────────────────
function addSet() {
    setCount++;
    const container = document.getElementById('sets-container');
    const row = document.createElement('div');
    row.className = 'set-row';
    row.id = `set-row-${setCount}`;
    row.innerHTML = `
        <span class="set-num">${setCount}</span>
        <input type="text" class="set-input" placeholder="0" id="set-weight-${setCount}" />
        <input type="text" class="set-input" placeholder="0" id="set-reps-${setCount}" />
        <input type="text" class="set-input" placeholder="optional" id="set-notes-${setCount}" />
        <button class="set-remove" onclick="removeSet(${setCount})"><i class="fa-solid fa-xmark"></i></button>`;
    container.appendChild(row);
}

function removeSet(id) {
    const row = document.getElementById(`set-row-${id}`);
    if (row) row.remove();
}

function collectSets() {
    const sets = [];
    document.querySelectorAll('.set-row').forEach(row => {
        const id = row.id.replace('set-row-', '');
        const weight = document.getElementById(`set-weight-${id}`)?.value || '';
        const reps = document.getElementById(`set-reps-${id}`)?.value || '';
        const notes = document.getElementById(`set-notes-${id}`)?.value || '';
        sets.push({ weight, reps, notes });
    });
    return sets;
}

async function submitWorkoutLog() {
    const category = document.getElementById('wk-category').value;
    const workout = document.getElementById('wk-exercise').value;
    const variations = document.getElementById('wk-variations').value;
    const duration = parseInt(document.getElementById('wk-duration').value) || 0;

    if (!category || !workout) {
        showToast('Please select a Category and Exercise.', 'error');
        return;
    }

    const sets = collectSets();
    const payload = { category, workout, variations, sets, duration_minutes: duration, is_custom: false };

    try {
        const res = await fetch('/api/workouts/log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) { const e = await res.json(); showToast(e.detail, 'error'); return; }
        const data = await res.json();
        showToast(data.message, 'success');

        // Reset form
        document.getElementById('wk-category').value = '';
        document.getElementById('wk-exercise').innerHTML = '<option value="">-- Select Exercise --</option>';
        document.getElementById('wk-variations').value = '';
        document.getElementById('wk-duration').value = '';
        document.getElementById('sets-container').querySelectorAll('.set-row').forEach(r => r.remove());
        setCount = 0;

        fetchStatus();
        fetchWorkoutHistory();
    } catch (err) { showToast('Error logging workout.', 'error'); }
}

async function fetchWorkoutHistory() {
    try {
        const res = await fetch('/api/workouts/history');
        if (!res.ok) return;
        renderWorkoutHistory(await res.json());
    } catch (err) { console.error('Error loading history:', err); }
}

function renderWorkoutHistory(logs) {
    const container = document.getElementById('workout-history-list');
    if (!container) return;
    container.innerHTML = '';

    if (!logs.length) {
        container.innerHTML = `<div class="empty-state">No workouts logged yet.</div>`;
        return;
    }

    logs.forEach(log => {
        const dt = new Date(log.Timestamp).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' });
        const entry = document.createElement('div');
        entry.className = 'workout-entry';
        entry.innerHTML = `
            <div class="workout-entry-header">
                <span class="workout-entry-name">${log.Workout || log.workout || 'N/A'}</span>
                <span class="workout-entry-cat">${log.Category || log.category || ''}</span>
            </div>
            <div class="workout-entry-meta">${dt} · ${log.Duration_Minutes || '0'} min · ${log.Sets || 'No sets'}</div>`;
        container.appendChild(entry);
    });
}

// ─── AI GOVERNANCE CHATBOT ──────────────────────────────────────────────────
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');

function quickPrompt(text) {
    if (chatInput) { chatInput.value = text; sendAIMessage(); }
}

function handleChatEnter(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAIMessage(); }
}

async function sendAIMessage() {
    const input = chatInput;
    if (!input) return;
    const message = input.value.trim();
    if (!message) return;

    const apiKey = localStorage.getItem('gemini_api_key') || '';

    // Append user bubble
    appendChatBubble(message, 'user');
    input.value = '';

    // Append thinking bubble
    const thinkingId = `thinking-${Date.now()}`;
    appendChatBubble('ANTIGRAVITY is analyzing...', 'ai', thinkingId, true);

    const sendBtn = document.getElementById('chat-send-btn');
    if (sendBtn) sendBtn.disabled = true;

    try {
        const res = await fetch('/api/ai/governance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, api_key: apiKey })
        });

        // Remove thinking bubble
        const thinkEl = document.getElementById(thinkingId);
        if (thinkEl) thinkEl.closest('.chat-bubble').remove();

        if (!res.ok) {
            const err = await res.json();
            appendChatBubble(`Error: ${err.detail}`, 'ai');
            return;
        }

        const data = await res.json();
        appendChatBubble(data.reply, 'ai');
    } catch (err) {
        const thinkEl = document.getElementById(thinkingId);
        if (thinkEl) thinkEl.closest('.chat-bubble').remove();
        appendChatBubble(`Connection error: ${err.message}. Make sure the server is running.`, 'ai');
    } finally {
        if (sendBtn) sendBtn.disabled = false;
        if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function appendChatBubble(text, role, id = '', isThinking = false) {
    if (!chatMessages) return;

    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role === 'ai' ? 'ai-bubble' : 'user-bubble'}`;

    const avatarIcon = role === 'ai' ? 'fa-robot' : 'fa-user';
    const name = role === 'ai' ? 'ANTIGRAVITY COACH' : 'BOOPATHI';

    // Format AI text (convert markdown-like to HTML)
    const formattedText = role === 'ai'
        ? text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>')
        : escapeHTML(text);

    bubble.innerHTML = `
        <div class="bubble-avatar"><i class="fa-solid ${avatarIcon}"></i></div>
        <div class="bubble-content">
            <div class="bubble-name">${name}</div>
            <div class="bubble-text ${isThinking ? 'thinking-bubble' : ''}" ${id ? `id="${id}"` : ''}>${formattedText}</div>
        </div>`;
    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHTML(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

// ─── SIDEBAR CHECK-IN BUTTON ────────────────────────────────────────────────
const btnManualCheckin = document.getElementById('btn-manual-checkin');
if (btnManualCheckin) {
    btnManualCheckin.addEventListener('click', async () => {
        btnManualCheckin.disabled = true;
        try {
            const res = await fetch('/api/trigger_checkin', { method: 'POST' });
            const data = await res.json();
            showToast(data.status === 'success' ? 'Check-in logged!' : 'Check-in cancelled.', data.status === 'success' ? 'success' : 'info');
            fetchLogs();
        } catch (err) { console.error(err); }
        finally { btnManualCheckin.disabled = false; }
    });
}

// ─── TOAST NOTIFICATIONS ─────────────────────────────────────────────────────
function showToast(message, type = 'info') {
    let toast = document.getElementById('toast-notif');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast-notif';
        toast.style.cssText = `
            position:fixed;bottom:1.5rem;right:1.5rem;z-index:9999;
            padding:0.75rem 1.25rem;border-radius:10px;
            font-size:0.875rem;font-weight:600;font-family:Inter,sans-serif;
            backdrop-filter:blur(16px);border:1px solid;
            display:flex;align-items:center;gap:0.5rem;
            max-width:320px;transition:all 0.3s;box-shadow:0 8px 32px rgba(0,0,0,0.5);
        `;
        document.body.appendChild(toast);
    }

    const styles = {
        success: { bg: 'rgba(16,185,129,0.2)', border: 'rgba(16,185,129,0.4)', color: '#34d399', icon: '✓' },
        error:   { bg: 'rgba(239,68,68,0.2)',  border: 'rgba(239,68,68,0.4)',  color: '#f87171', icon: '✕' },
        info:    { bg: 'rgba(59,130,246,0.2)', border: 'rgba(59,130,246,0.4)', color: '#60a5fa', icon: 'ℹ' }
    };
    const s = styles[type] || styles.info;
    toast.style.background = s.bg;
    toast.style.borderColor = s.border;
    toast.style.color = s.color;
    toast.innerHTML = `<span>${s.icon}</span><span>${message}</span>`;
    toast.style.opacity = '1'; toast.style.transform = 'translateY(0)';

    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => {
        toast.style.opacity = '0'; toast.style.transform = 'translateY(10px)';
    }, 3500);
}

// ─── INITIALIZATION ─────────────────────────────────────────────────────────
async function initializeDashboard() {
    await fetchStatus();
    // Load syllabus eagerly for Gate progress bars on dashboard
    await fetchSyllabus();
    await fetchLogs();
}

window.addEventListener('DOMContentLoaded', initializeDashboard);
setInterval(fetchStatus, 30000);
setInterval(fetchLogs, 30000);

