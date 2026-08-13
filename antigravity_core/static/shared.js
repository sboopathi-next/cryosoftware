/* ── SHARED NAV + UTILITIES ─────────────────────────────────
   Loaded on every page. Handles:
   - Active nav link highlighting
   - Toast notifications
   - Settings modal (API key)
   - Stats mini-bar fetch
   - Auth token injection (Bearer token on all API calls)
──────────────────────────────────────────────────────────── */

// ── Auth helpers ──────────────────────────────────────────────────────────────
const AG_TOKEN_KEY = 'ag_token';

function getAuthToken() {
  return localStorage.getItem(AG_TOKEN_KEY) || '';
}

/**
 * Authenticated fetch — wraps window.fetch to auto-inject the Bearer token.
 * Falls back gracefully when offline or no token is stored.
 * Redirects to /login on 401.
 */
async function apiFetch(url, options = {}) {
  const token = getAuthToken();
  const headers = { ...(options.headers || {}) };
  if (token && token !== 'offline') {
    headers['Authorization'] = 'Bearer ' + token;
  }
  const resp = await fetch(url, { ...options, headers });
  if (resp.status === 401) {
    // Token expired / invalid — clear and redirect to login
    localStorage.removeItem(AG_TOKEN_KEY);
    if (!window.location.pathname.startsWith('/login')) {
      window.location.replace('/login');
    }
    throw new Error('Unauthorized — redirecting to login.');
  }
  return resp;
}

// Guard: on every page load, silently verify the token.
// If server says 401 → redirect to /login. If offline → pass through.
(function _authGuard() {
  // Skip guard on the login page itself
  if (window.location.pathname.startsWith('/login')) return;

  const token = getAuthToken();
  // No token at all: if offline (server unreachable) → stay; if online → go to login
  fetch('/api/auth/check', {
    headers: token ? { 'Authorization': 'Bearer ' + token } : {}
  }).then(r => {
    if (r.status === 401) {
      localStorage.removeItem(AG_TOKEN_KEY);
      window.location.replace('/login');
    }
  }).catch(() => {
    // Server unreachable (offline) — auth is bypassed server-side too, stay on page
  });
})();

// ── Active nav link ──────────────────────────────────────────

(function () {
  const path = window.location.pathname.replace(/\/$/, '') || '/';
  document.querySelectorAll('.nav a').forEach(a => {
    const href = a.getAttribute('href').replace(/\/$/, '') || '/';
    if (href === path) a.classList.add('active');
  });
})();

function escHTML(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ── Toast ────────────────────────────────────────────────────
function toast(msg, type = 'info') {
  let el = document.getElementById('toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toast';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.className = type === 'ok' ? 'ok' : type === 'err' ? 'err' : 'info';
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add('hide'), 3200);
}

// ── Groq Models ─────────────────────────────────────────────────────────────
const DECOMMISSIONED_MODELS_JS = [
  'llama3-70b-8192', 'llama3-8b-8192'
];

function getSanitizedGroqModel() {
  let m = localStorage.getItem('groq_model');
  if (!m || DECOMMISSIONED_MODELS_JS.includes(m) || m.includes('openai/')) {
    m = 'llama-3.3-70b-versatile';
    localStorage.setItem('groq_model', m);
    localStorage.setItem('studio_model', m);
  }
  return m;
}

const GROQ_MODELS = [
  { value: 'llama-3.3-70b-versatile', label: 'llama-3.3-70b-versatile 🔥 Flagship (70B)' },
  { value: 'llama-3.1-8b-instant', label: 'llama-3.1-8b-instant ⚡ Fast (8B)' },
  { value: 'gemma2-9b-it', label: 'gemma2-9b-it 🎯 Google Gemma' },
  { value: 'mixtral-8x7b-32768', label: 'mixtral-8x7b-32768 🌀 Mixtral 8x7B' }
];

function _buildGroqModelOptions(selected) {
  let html = '<optgroup label="🚀 Groq Models (Ultra-Fast Hardware)">';
  for (const m of GROQ_MODELS) {
    html += `<option value="${m.value}" ${selected === m.value ? 'selected' : ''}>${escHTML(m.label)}</option>`;
  }
  html += '</optgroup>';
  return html;
}

// ── Settings modal ───────────────────────────────────────────
function openSettings() {
  const m = document.getElementById('settings-modal');
  if (!m) return;

  const currentKey = localStorage.getItem('groq_key') || localStorage.getItem('gemini_key') || '';
  let currentModel = getSanitizedGroqModel();

  m.innerHTML = `
    <div class="modal" style="max-width: 480px; width: 90%;">
      <div class="modal-hd">
        <span><i class="fa-solid fa-bolt" style="color:var(--cyan);margin-right:6px"></i> Groq AI Settings</span>
        <button class="modal-close" onclick="closeSettings()"><i class="fa-solid fa-xmark"></i></button>
      </div>
      <div class="modal-body" style="padding: 16px; display: flex; flex-direction: column; gap: 12px;">
        <p class="text-muted" style="font-size: 11px; margin-bottom: 8px; color: var(--text3);">
          Get a free Groq API key from <a href="https://console.groq.com/keys" target="_blank" style="color:var(--cyan); text-decoration: underline;">console.groq.com/keys</a>
        </p>
        <div class="field">
          <label>GROQ API KEY</label>
          <input type="password" id="api-key-inp" value="${escHTML(currentKey)}" placeholder="gsk_..." style="background:#0a0d1e; border:1px solid var(--border); border-radius:6px; color:var(--text1); padding:8px 12px; outline:none; font-size:13px; font-family:var(--ff-body); width:100%;">
        </div>
        <div class="field mt-1">
          <label>GROQ MODEL</label>
          <select id="studio-model-sel" style="background:#0a0d1e; border:1px solid var(--border); border-radius:6px; color:var(--text1); padding:8px 12px; outline:none; font-size:13px; font-family:var(--ff-body); width:100%;">
            ${_buildGroqModelOptions(currentModel)}
          </select>
          <div style="font-size:10px; color:#10b981; margin-top:4px;">🚀 Ultra-fast inference provided by Groq LPU hardware</div>
        </div>

        <div class="field mt-1">
          <label>Voice Demon Test</label>
          <button id="test-voice-btn" class="btn btn-secondary btn-full" onclick="testVoiceDemon()">
            <i class="fa-solid fa-bullhorn" style="color:var(--cyan)"></i> Test Voice Demon Audio
          </button>
        </div>

        <button class="btn btn-primary btn-full mt-2" onclick="saveWorkstationSettings()"><i class="fa-solid fa-floppy-disk"></i> Save Settings</button>
      </div>
    </div>
  `;
  m.classList.remove('hidden');
  m.style.display = 'flex';
}

async function saveWorkstationSettings() {
  const groqKey = (document.getElementById('api-key-inp')?.value || '').trim();
  const groqModel = document.getElementById('studio-model-sel')?.value || 'llama-3.3-70b-versatile';

  localStorage.setItem('groq_key', groqKey);
  localStorage.setItem('groq_model', groqModel);
  // Keep legacy key synced so existing code reads it seamlessly
  localStorage.setItem('gemini_key', groqKey);
  localStorage.setItem('studio_model', groqModel);

  if (groqKey) {
    try {
      await fetch('/api/settings/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ groq_api_key: groqKey, groq_model: groqModel })
      });
    } catch (e) {
      console.warn('[Settings] Could not sync Groq API key to server DB:', e);
    }
  }

  closeSettings();
  toast('Settings saved! Groq AI Engine activated.', 'ok');

  const notice = document.getElementById('key-notice');
  if (notice) {
    if (groqKey) {
      notice.classList.add('hidden');
    } else {
      notice.classList.remove('hidden');
    }
  }
}

function closeSettings() {
  const m = document.getElementById('settings-modal');
  if (m) {
    m.classList.add('hidden');
    m.style.display = 'none';
  }
}

/** Logout: clear token and go to login page */
function logout() {
  localStorage.removeItem(AG_TOKEN_KEY);
  window.location.replace('/login');
}

// ── Voice Demon AI Engine — Stoic & Discipline Phrase Banks ──────
const STOIC_PHRASE_BANKS = {
  RUTHLESS_DISCIPLINE: [
    "Boopathi... Your competitors are studying while you negotiate with comfort.",
    "Discipline begins where motivation ends.",
    "Comfort is expensive. Discipline is cheaper.",
    "The work doesn't care how you feel.",
    "Execute the plan. Ignore the emotion.",
    "The clock moves whether you do or not.",
    "Your future self is watching today's decisions.",
    "Earn your confidence through action.",
    "Stop explaining. Start producing.",
    "Action destroys anxiety.",
    "Weak habits build weak lives.",
    "One more excuse. One less opportunity.",
    "The mind obeys the habits you train.",
    "Choose discomfort today or regret tomorrow.",
    "Master yourself before trying to master anything else."
  ],
  MARCUS_STYLE: [
    "You control your effort, Boopathi, not the outcome.",
    "Do what is necessary. Nothing more. Nothing less.",
    "Waste no time arguing what excellence is. Become it.",
    "Your duty exists independent of your mood.",
    "The obstacle is not your enemy. It is your teacher.",
    "Nothing external can weaken a disciplined mind.",
    "Meet every task as if it defines your character.",
    "The universe owes you nothing. Earn everything.",
    "Character is built in ordinary moments.",
    "Do not seek an easier life. Become stronger."
  ],
  WARRIOR: [
    "Boopathi... Today you conquer yourself or you surrender to yourself.",
    "Every rep is a vote for the man you're becoming.",
    "Pain leaves. Weakness negotiates.",
    "Stand up. Finish what you started.",
    "Champions are built when nobody is watching.",
    "Your enemy is comfort.",
    "Attack the task before the task attacks your confidence.",
    "A warrior measures effort, not excuses.",
    "No shortcuts. No negotiations.",
    "You don't need permission to become dangerous."
  ],
  STUDY_MODE: [
    "One theorem mastered today beats ten videos watched.",
    "Read. Think. Solve. Repeat.",
    "Every bug solved sharpens your mind, Boopathi.",
    "Every proof understood increases your advantage for GATE 2028.",
    "Concepts create ranks. Memorization creates disappointment.",
    "Debug your code. Debug your mind.",
    "One page more. One problem more.",
    "Consistency beats intelligence without discipline.",
    "Knowledge compounds daily.",
    "Small improvements become elite performance."
  ],
  COLD_REALITY: [
    "Time will pass whether you improve or not, Boopathi.",
    "Nobody can study on your behalf.",
    "Potential without execution is fiction.",
    "Results remember actions, not intentions.",
    "Your habits write your future.",
    "The mirror never lies.",
    "Progress cannot be outsourced.",
    "Excuses produce identical results every time: nothing.",
    "Your calendar reveals your priorities.",
    "Respect is earned through consistency."
  ],
  REAL_STOICS: [
    "Waste no more time arguing what a good man should be. Be one. Marcus Aurelius.",
    "We suffer more often in imagination than in reality. Seneca.",
    "No man is free who is not master of himself. Epictetus.",
    "Difficulties strengthen the mind. Seneca.",
    "It is not what happens to you, but how you react to it that matters. Epictetus.",
    "The impediment to action advances action. Marcus Aurelius.",
    "First say to yourself what you would be; then do what you have to do. Epictetus.",
    "Luck is what happens when preparation meets opportunity. Seneca.",
    "If it is not right, do not do it. If it is not true, do not say it. Marcus Aurelius.",
    "He who fears death will never do anything worthy of a living man. Seneca."
  ],
  SYSTEM: [
    "System message. Emotional interference detected. Returning control to logic.",
    "System message. Discipline increased by one percent. Continue execution.",
    "System message. Comfort protocol rejected.",
    "System message. Mission priority: Complete today's objectives.",
    "System message. Willpower reserve restored through action.",
    "System message. Excuse rejected. Continue.",
    "System message. Identity updated: One who finishes.",
    "System message. Momentum acquired.",
    "System message. Focus stabilized.",
    "System message. Execute. Evaluate. Improve."
  ]
};

const STOIC_PHRASES = Object.values(STOIC_PHRASE_BANKS).flat();

function isVoiceMuted() {
  return localStorage.getItem('ag_voice_muted') === 'true';
}

function toggleVoiceMute() {
  const muted = !isVoiceMuted();
  localStorage.setItem('ag_voice_muted', muted ? 'true' : 'false');
  if (muted && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
  updateVoiceUI();
  toast(muted ? 'Voice Demon Muted 🔇' : 'Voice Demon Activated 🔊', muted ? 'info' : 'ok');
  if (!muted) {
    speakVoice("Voice Demon online. Ready, Boopathi.");
  }
}

function primeSpeechSynthesis() {
  if (!('speechSynthesis' in window) || isVoiceMuted()) return;
  try {
    const dummy = new SpeechSynthesisUtterance(' ');
    dummy.volume = 0.01;
    window.speechSynthesis.speak(dummy);
  } catch (_) { }
}

function cleanTextForSpeech(text) {
  if (!text) return "";
  return text
    .replace(/\[\s*AI GOVERNANCE DECREE\s*\][\s\S]*$/gi, '') // strip governance decree footer
    .replace(/\$\$[\s\S]*?\$\$/g, ' math equation ')          // remove display math
    .replace(/\\\[[\s\S]*?\\\]/g, ' math equation ')
    .replace(/\$[^\$\n]+?\$/g, ' math term ')                // remove inline math
    .replace(/\\\([\s\S]*?\\\)/g, ' math term ')
    .replace(/```[\s\S]*?```/g, ' code block ')              // remove code blocks
    .replace(/`([^`]+)`/g, '$1')                             // inline code
    .replace(/^#+\s+/gm, '')                                 // strip headers
    .replace(/[*#_~>•]/g, '')                                // markdown formatting
    .replace(/<[^>]*>/g, '')                                 // html tags
    .replace(/\|[\s\S]*?\|/g, ' ')                           // markdown tables
    .replace(/\s+/g, ' ')                                    // normalize spaces
    .trim();
}

function extractValuableAISpeech(replyText) {
  if (!replyText) return "";
  const rawClean = cleanTextForSpeech(replyText);
  if (!rawClean) return "";

  // Split into sentences
  const sentences = rawClean.match(/[^.!?]+[.!?]+/g) || [rawClean];

  // Filter out standalone titles/headers (e.g., "TODAYS BATTLE PLAN", "THE ENGINE OF ALL MACHINE LEARNING")
  const valuableSentences = sentences.filter(s => {
    const trimmed = s.trim();
    if (trimmed.length < 15) return false;
    if (/^(TODAY'S BATTLE PLAN|SYSTEM GOVERNANCE DECREE|THE ENGINE OF ALL|CURRENT STREAK|ACTIVE SUBJECT)/i.test(trimmed)) return false;
    return true;
  });

  const selected = (valuableSentences.length > 0 ? valuableSentences : sentences).slice(0, 7);
  return selected.join(' ');
}

function speakVoice(text, forceInterrupt = false, moodObj = null) {
  if (isVoiceMuted()) return;
  if (!('speechSynthesis' in window)) return;

  const clean = cleanTextForSpeech(text);
  if (!clean) return;

  if (forceInterrupt) {
    window.speechSynthesis.cancel();
  }

  const utter = new SpeechSynthesisUtterance(clean);
  utter.volume = 1.0;

  // Detect mobile device
  const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

  // Dynamic Voice Selection matching Coach Mood
  const allVoices = window.speechSynthesis.getVoices();
  const enVoices = allVoices.filter(v => v.lang.startsWith('en'));

  if (enVoices.length > 0) {
    const targetPitch = moodObj && moodObj.pitch ? moodObj.pitch : null;
    const targetRate = moodObj && moodObj.rate ? moodObj.rate : null;

    const pickFemale = (moodObj && moodObj.gender === 'female') ? true :
      (moodObj && moodObj.gender === 'male') ? false :
        ((moodObj && moodObj.warmth > 6) ? true : (Math.random() < 0.4));
    let selectedVoice = null;

    if (pickFemale) {
      selectedVoice = enVoices.find(v =>
        v.name.includes('Female') || v.name.includes('Zira') || v.name.includes('Hazel') ||
        v.name.includes('Samantha') || v.name.includes('Victoria') || v.name.includes('Google UK English Female')
      );
      if (selectedVoice) {
        utter.voice = selectedVoice;
        if (isMobile) {
          utter.pitch = targetPitch || 0.95;
          utter.rate = targetRate || 1.0;
        } else {
          utter.pitch = targetPitch || (0.62 + (Math.random() * 0.1));
          utter.rate = targetRate || 0.92;
        }
      }
    }

    if (!selectedVoice) {
      selectedVoice = enVoices.find(v =>
        v.name.includes('Male') || v.name.includes('David') || v.name.includes('James') ||
        v.name.includes('George') || v.name.includes('Google UK English Male')
      ) || enVoices[0];
      if (selectedVoice) {
        utter.voice = selectedVoice;
        if (isMobile) {
          utter.pitch = targetPitch || 0.88;
          utter.rate = targetRate || 0.95;
        } else {
          utter.pitch = targetPitch || (0.35 + (Math.random() * 0.12));
          utter.rate = targetRate || 0.85;
        }
      }
    }
  } else {
    if (isMobile) {
      utter.pitch = moodObj && moodObj.pitch ? moodObj.pitch : 0.95;
      utter.rate = moodObj && moodObj.rate ? moodObj.rate : 1.0;
    } else {
      utter.pitch = moodObj && moodObj.pitch ? moodObj.pitch : 0.45;
      utter.rate = moodObj && moodObj.rate ? moodObj.rate : 0.88;
    }
  }

  window.speechSynthesis.speak(utter);
}

function speakAIResponse(replyText, moodObj = null) {
  if (isVoiceMuted() || !replyText) return;
  const valuableSpeech = extractValuableAISpeech(replyText);
  if (valuableSpeech) {
    speakVoice(valuableSpeech, true, moodObj);
  }
}

function testVoiceDemon() {
  speakVoice("Greetings Boopathi. I am your Voice Demon. Ready to conquer GATE 2028.", true);
}

function checkLevelUpEvent(newLevel) {
  const lastLevelStr = localStorage.getItem('ag_last_level');
  if (lastLevelStr !== null) {
    const lastLevel = parseInt(lastLevelStr, 10);
    if (!isNaN(lastLevel) && newLevel > lastLevel) {
      speakVoice(`Hey Boopathi! You are leveling up! Welcome to Level ${newLevel}. Great work!`, true);
      toast(`LEVEL UP! Welcome to Level ${newLevel}! 🎉`, 'ok');
    }
  }
  localStorage.setItem('ag_last_level', newLevel.toString());
}

function renderVoiceControls() {
  const footer = document.querySelector('.sidebar-footer');
  if (!footer) return;

  if (document.getElementById('voice-toggle-btn')) {
    updateVoiceUI();
    return;
  }

  const btn = document.createElement('button');
  btn.id = 'voice-toggle-btn';
  btn.className = 'btn-ico';
  btn.title = 'Toggle Voice Demon (Click to Mute/Unmute)';
  btn.onclick = toggleVoiceMute;

  const settingsBtn = footer.querySelector('button');
  if (settingsBtn) {
    footer.insertBefore(btn, settingsBtn);
  } else {
    footer.appendChild(btn);
  }

  updateVoiceUI();
}

function updateVoiceUI() {
  const btn = document.getElementById('voice-toggle-btn');
  if (!btn) return;
  const muted = isVoiceMuted();
  btn.innerHTML = muted ? '<i class="fa-solid fa-volume-xmark" style="color:var(--text3)"></i>' : '<i class="fa-solid fa-volume-high" style="color:var(--cyan)"></i>';
  btn.style.borderColor = muted ? 'var(--border)' : 'var(--cyan)';
  btn.style.boxShadow = muted ? 'none' : '0 0 10px rgba(6,182,212,0.3)';
}

function startVoiceDaemonTimer() {
  if (window._voiceDaemonTimerStarted) return;
  window._voiceDaemonTimerStarted = true;

  setInterval(() => {
    if (!isVoiceMuted()) {
      const phrase = STOIC_PHRASES[Math.floor(Math.random() * STOIC_PHRASES.length)];
      speakVoice(phrase);
    }
  }, 12 * 60 * 1000);
}

// Preload voices
if ('speechSynthesis' in window) {
  window.speechSynthesis.onvoiceschanged = () => { window.speechSynthesis.getVoices(); };
}

// ── Mini stats bar — floating top-right corner (Draggable & Movable) ────────
function injectFloatingStatsBar() {
  if (document.getElementById('ag-stats-bar')) return;
  const bar = document.createElement('div');
  bar.id = 'ag-stats-bar';
  bar.style.cssText = [
    'position:fixed', 'top:12px', 'right:16px', 'z-index:1005',
    'display:flex', 'align-items:center', 'gap:6px',
    'background:rgba(6,8,24,0.88)', 'backdrop-filter:blur(12px)',
    'border:1px solid rgba(99,102,241,0.3)', 'border-radius:30px',
    'padding:5px 12px', 'box-shadow:0 6px 24px rgba(0,0,0,0.6)',
    'font-family:var(--ff-mono)', 'font-size:11px', 'color:var(--text2)',
    'pointer-events:auto', 'user-select:none', 'touch-action:none'
  ].join(';');
  bar.innerHTML = `
    <span class="drag-handle" style="cursor:grab; color:var(--text3); display:flex; align-items:center; margin-right:2px;" title="Drag to move"><i class="fa-solid fa-grip-vertical" style="font-size:10px"></i></span>
    <span style="color:var(--indigo);font-weight:700;letter-spacing:.05em;"><i class="fa-solid fa-microchip" style="font-size:10px"></i></span>
    <span style="color:var(--text3)">Lv</span><span id="hdr-lvl" style="color:var(--cyan);font-weight:700">—</span>
    <span style="color:var(--border)">|</span>
    <span id="hdr-energy" style="color:var(--green)">—%</span>
    <span style="color:var(--border)">|</span>
    <i class="fa-solid fa-fire" style="color:var(--amber);font-size:9px"></i>
    <span id="hdr-streak" style="color:var(--amber)">0d</span>
    <span style="color:var(--border)">|</span>
    <button id="sync-status-btn" onclick="triggerManualSync()" title="Neon DB Sync Status (Click to Sync)" style="background:none; border:none; color:var(--text2); font-family:var(--ff-mono); font-size:11px; cursor:pointer; display:flex; align-items:center; gap:4px; outline:none; padding: 2px 6px; border-radius: 12px; transition: background 0.2s;">
      <i id="sync-icon" class="fa-solid fa-circle" style="color:var(--green); font-size:8px;"></i>
      <span id="sync-text">Online</span>
    </button>
  `;
  document.body.appendChild(bar);
  makeElementDraggable(bar);
}

function makeElementDraggable(elmnt) {
  let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
  const savedPos = localStorage.getItem('ag_stats_bar_pos');
  if (savedPos) {
    try {
      const { top, left } = JSON.parse(savedPos);
      if (top !== undefined && left !== undefined) {
        elmnt.style.top = top + 'px';
        elmnt.style.left = left + 'px';
        elmnt.style.right = 'auto';
      }
    } catch (e) { }
  }

  const dragHandle = elmnt.querySelector('.drag-handle') || elmnt;
  dragHandle.addEventListener('mousedown', dragMouseDown);
  dragHandle.addEventListener('touchstart', dragTouchStart, { passive: false });

  function dragMouseDown(e) {
    if (e.target.tagName === 'BUTTON' || e.target.closest('button')) return;
    e.preventDefault();
    pos3 = e.clientX;
    pos4 = e.clientY;
    document.addEventListener('mouseup', closeDragElement);
    document.addEventListener('mousemove', elementDrag);
    dragHandle.style.cursor = 'grabbing';
  }

  function elementDrag(e) {
    e.preventDefault();
    pos1 = pos3 - e.clientX;
    pos2 = pos4 - e.clientY;
    pos3 = e.clientX;
    pos4 = e.clientY;
    let newTop = elmnt.offsetTop - pos2;
    let newLeft = elmnt.offsetLeft - pos1;
    newTop = Math.max(5, Math.min(window.innerHeight - 45, newTop));
    newLeft = Math.max(5, Math.min(window.innerWidth - 160, newLeft));
    elmnt.style.top = newTop + "px";
    elmnt.style.left = newLeft + "px";
    elmnt.style.right = 'auto';
  }

  function closeDragElement() {
    document.removeEventListener('mouseup', closeDragElement);
    document.removeEventListener('mousemove', elementDrag);
    dragHandle.style.cursor = 'grab';
    localStorage.setItem('ag_stats_bar_pos', JSON.stringify({ top: elmnt.offsetTop, left: elmnt.offsetLeft }));
  }

  function dragTouchStart(e) {
    if (e.target.tagName === 'BUTTON' || e.target.closest('button')) return;
    const touch = e.touches[0];
    pos3 = touch.clientX;
    pos4 = touch.clientY;
    document.addEventListener('touchend', closeTouchElement);
    document.addEventListener('touchmove', elementTouchMove, { passive: false });
  }

  function elementTouchMove(e) {
    e.preventDefault();
    const touch = e.touches[0];
    pos1 = pos3 - touch.clientX;
    pos2 = pos4 - touch.clientY;
    pos3 = touch.clientX;
    pos4 = touch.clientY;
    let newTop = elmnt.offsetTop - pos2;
    let newLeft = elmnt.offsetLeft - pos1;
    newTop = Math.max(5, Math.min(window.innerHeight - 45, newTop));
    newLeft = Math.max(5, Math.min(window.innerWidth - 160, newLeft));
    elmnt.style.top = newTop + "px";
    elmnt.style.left = newLeft + "px";
    elmnt.style.right = 'auto';
  }

  function closeTouchElement() {
    document.removeEventListener('touchend', closeTouchElement);
    document.removeEventListener('touchmove', elementTouchMove);
    localStorage.setItem('ag_stats_bar_pos', JSON.stringify({ top: elmnt.offsetTop, left: elmnt.offsetLeft }));
  }
}

async function syncLeetCodeManual() {
  const btn = document.getElementById('leetcode-sync-btn');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Syncing...</span>';
  }
  toast('⚡ Querying LeetCode API (IST Timezone Check)...', 'info');

  try {
    const r = await apiFetch('/api/leetcode/sync', { method: 'POST' });
    const d = await r.json();

    if (d.status === 'success') {
      const solved = d.solved_today;
      const xp = d.xp_awarded || 0;
      const str = d.str_awarded || 0;

      if (solved || xp > 0) {
        toast(`🔥 LeetCode Synced! Solved Today: YES (+${xp} XP, +${str} STR)`, 'ok');
      } else {
        toast(`⚡ LeetCode Checked! All: ${d.current_stats?.All || 0} solved. No new solves today yet.`, 'info');
      }

      const chk = document.getElementById('chk-leetcode');
      if (chk && (solved || d.leetcode_completed)) {
        chk.classList.add('auto-checked');
      }
      if (window.loadDashboard) window.loadDashboard();
      if (window.fetchMiniStats) window.fetchMiniStats();
    } else {
      toast('LeetCode sync error: ' + (d.message || 'Check connection'), 'err');
    }
  } catch (e) {
    toast('LeetCode sync request failed: ' + e.message, 'err');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-code" style="font-size:9px;"></i> <span>LeetCode</span>';
    }
  }
}

// ── Google Fit Cloud API Sync ────────────────────────────────
async function syncGoogleFitCloudManual(btnEl = null) {
  const btn = btnEl || document.getElementById('googlefit-sync-btn');
  let originalHTML = '';
  if (btn) {
    originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Syncing...</span>';
  }
  toast('🏃 Querying Google Fit Cloud API...', 'info');

  try {
    const res = await apiFetch('/api/health_sync/google_fit', { method: 'POST' });
    const d = await res.json();

    if (d.setup_required) {
      toast('⚠️ Google Fit Setup Needed: ' + d.message, 'warn');
      if (window.openHealthSyncModal) window.openHealthSyncModal();
    } else if (d.status === 'SUCCESS' || d.steps !== undefined) {
      const stepsFormatted = (d.steps || 0).toLocaleString();
      toast(`✅ Google Fit Synced! ${stepsFormatted} steps (${d.distance_km || 0} km) | +${d.xp_awarded || 0} XP, +${d.wil_gained || 0} WIL!`, 'ok');

      const chkHealth = document.getElementById('chk-health');
      if (chkHealth) chkHealth.classList.add('done');

      if ((d.steps >= 1000 || (d.distance_km && d.distance_km >= 0.5)) && document.getElementById('chk-walk')) {
        document.getElementById('chk-walk').classList.add('done');
      }

      if (window.loadDashboard) window.loadDashboard();
      if (window.loadMiniStats) window.loadMiniStats();
      if (window.closeHealthSyncModal) window.closeHealthSyncModal();
    } else {
      toast('Google Fit Sync: ' + (d.message || JSON.stringify(d)), 'err');
    }
  } catch (e) {
    toast('Google Fit Sync Error: ' + e.message, 'err');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHTML || '<i class="fa-solid fa-rotate"></i> <span>Sync Fit</span>';
    }
  }
}

window.syncViaGoogleFitCloud = syncGoogleFitCloudManual;
window.syncGoogleFitCloudManual = syncGoogleFitCloudManual;

// ── Mobile Bottom Nav & Sheet Injection ───────────────────────
function injectMobileNavigation() {
  if (document.querySelector('.mobile-bottom-nav')) return;

  // 1. Create and inject bottom nav container (1. Dashboard, 2. Canvas, 3. GymPro, 4. MindOS, 5. More)
  const bottomNav = document.createElement('div');
  bottomNav.className = 'mobile-bottom-nav';
  bottomNav.innerHTML = `
    <a href="/" class="mobile-nav-item" data-path="/"><i class="fa-solid fa-gauge-high"></i><span>Dashboard</span></a>
    <a href="/canvas" class="mobile-nav-item" data-path="/canvas"><i class="fa-solid fa-graduation-cap" style="color:var(--cyan)"></i><span>Canvas</span></a>
    <a href="/gym-pro" class="mobile-nav-item" data-path="/gym-pro"><i class="fa-solid fa-bolt" style="color:var(--amber)"></i><span>Gym Pro</span></a>
    <a href="/mind-os" class="mobile-nav-item" data-path="/mind-os"><i class="fa-solid fa-brain" style="color:var(--purple)"></i><span>Mind OS</span></a>
    <button class="mobile-nav-item" id="mobile-more-btn"><i class="fa-solid fa-bars"></i><span>More</span></button>
  `;
  document.body.appendChild(bottomNav);

  // 2. Create and inject overlay and sheet drawer (holding all remaining module links)
  const overlay = document.createElement('div');
  overlay.className = 'mobile-bottom-sheet-overlay';
  overlay.id = 'mobile-sheet-overlay';
  document.body.appendChild(overlay);

  const sheet = document.createElement('div');
  sheet.className = 'mobile-bottom-sheet';
  sheet.id = 'mobile-sheet';
  sheet.innerHTML = `
    <div class="sheet-header">
      <div class="sheet-handle"></div>
      <div class="sheet-title">More Modules</div>
      <button class="sheet-close" id="mobile-sheet-close"><i class="fa-solid fa-xmark"></i></button>
    </div>
    <div class="sheet-body">
      <div class="sheet-grid">
        <a href="/syllabus" class="sheet-grid-item"><i class="fa-solid fa-book-open" style="color:var(--indigo)"></i><span>Study Path</span></a>
        <a href="/gym" class="sheet-grid-item"><i class="fa-solid fa-dumbbell" style="color:var(--amber)"></i><span>Gym Tracker</span></a>
        <a href="/system" class="sheet-grid-item"><i class="fa-solid fa-gamepad" style="color:var(--rose)"></i><span>System OS</span></a>
        <a href="/journal" class="sheet-grid-item"><i class="fa-solid fa-pen-to-square"></i><span>Study Journal</span></a>
        <a href="/english" class="sheet-grid-item"><i class="fa-solid fa-language" style="color:var(--cyan)"></i><span>English Booster</span></a>
        <a href="/badlog" class="sheet-grid-item"><i class="fa-solid fa-fire-flame-curved" style="color:#ef4444"></i><span>Rage Fuel</span></a>
        <a href="/stoic" class="sheet-grid-item"><i class="fa-solid fa-crown" style="color:var(--amber)"></i><span>Stoic Log</span></a>
        <a href="/human" class="sheet-grid-item"><i class="fa-solid fa-heart" style="color:var(--red)"></i><span>Human Journal</span></a>
        <a href="/logs" class="sheet-grid-item"><i class="fa-solid fa-list-check"></i><span>Activity Logs</span></a>
        <a href="/news" class="sheet-grid-item"><i class="fa-solid fa-newspaper" style="color:var(--blue)"></i><span>Tech News</span></a>
        <a href="/exam" class="sheet-grid-item"><i class="fa-solid fa-square-root-variable" style="color:var(--indigo)"></i><span>Exam Editor</span></a>
        <a href="/teacher" class="sheet-grid-item"><i class="fa-solid fa-graduation-cap" style="color:#10b981"></i><span>AI Teacher</span></a>
        <a href="/teach" class="sheet-grid-item"><i class="fa-solid fa-chalkboard-user" style="color:#818cf8"></i><span>Teaching Log</span></a>
        <a href="/work-tracker" class="sheet-grid-item"><i class="fa-solid fa-briefcase" style="color:var(--indigo)"></i><span>Work Tracker</span></a>
        <a href="#" onclick="openSettings(); return false;" class="sheet-grid-item"><i class="fa-solid fa-gear" style="color:var(--text2)"></i><span>Settings</span></a>
      </div>
    </div>
  `;
  document.body.appendChild(sheet);

  // 3. Highlight current path
  const currentPath = window.location.pathname.replace(/\/$/, '') || '/';
  bottomNav.querySelectorAll('.mobile-nav-item').forEach(item => {
    const path = item.getAttribute('data-path');
    if (path === currentPath || (path === '/gym-pro' && (currentPath === '/gym_pro' || currentPath === '/gym-pro.html'))) {
      item.classList.add('active');
    }
  });

  sheet.querySelectorAll('.sheet-grid-item').forEach(item => {
    const href = item.getAttribute('href');
    if (href && href !== '#' && href.replace(/\/$/, '') === currentPath) {
      item.style.borderColor = 'var(--cyan)';
      item.style.background = 'rgba(6, 182, 212, 0.08)';
      item.querySelector('span').style.color = '#ffffff';
    }
  });

  // 4. Bind Toggle events
  const moreBtn = document.getElementById('mobile-more-btn');
  const closeBtn = document.getElementById('mobile-sheet-close');

  function openSheet() {
    overlay.classList.add('active');
    sheet.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function closeSheet() {
    overlay.classList.remove('active');
    sheet.classList.remove('active');
    document.body.style.overflow = '';
  }

  if (moreBtn) moreBtn.addEventListener('click', openSheet);
  if (closeBtn) closeBtn.addEventListener('click', closeSheet);
  if (overlay) overlay.addEventListener('click', closeSheet);
}

async function triggerManualSync() {
  const btn = document.getElementById('sync-status-btn');
  const icon = document.getElementById('sync-icon');
  const text = document.getElementById('sync-text');
  if (!btn) return;

  btn.disabled = true;
  const originalClass = icon ? icon.className : 'fa-solid fa-circle';
  const originalColor = icon ? icon.style.color : 'var(--green)';
  const originalText = text ? text.textContent : 'Online';

  if (icon) {
    icon.className = 'fa-solid fa-rotate fa-spin';
    icon.style.color = 'var(--cyan)';
  }
  if (text) text.textContent = 'Syncing...';

  try {
    const r = await apiFetch('/api/sync/trigger', { method: 'POST' });
    const d = await r.json();
    if (r.ok && d.status === 'success') {
      toast('Neon database synchronized successfully! 🎉', 'ok');
      await loadMiniStats();
    } else {
      toast('Sync failed: ' + (d.message || 'database unreachable'), 'err');
      if (icon) {
        icon.className = originalClass;
        icon.style.color = originalColor;
      }
      if (text) text.textContent = originalText;
    }
  } catch (e) {
    toast('Sync failed: Network error', 'err');
    if (icon) {
      icon.className = originalClass;
      icon.style.color = originalColor;
    }
    if (text) text.textContent = originalText;
  } finally {
    btn.disabled = false;
  }
}

// ── Dashboard Sub-Tabs for Mobile ────────────────────────────
function initDashboardMobileTabs() {
  // Only execute on main dashboard page on mobile screens (width <= 768)
  if (window.innerWidth > 768) return;
  const pathname = window.location.pathname.replace(/\/$/, '') || '/';
  if (pathname !== '/' && pathname !== '/index.html') return;

  const main = document.querySelector('.main');
  if (!main) return;

  const statsGrid = document.querySelector('.stats-grid');
  const cards = Array.from(main.querySelectorAll(':scope > .card'));

  if (!statsGrid || cards.length < 1) return;

  // Stats Grid and Daily Checklist (cards[0])
  const checklistCard = cards[0];

  statsGrid.classList.add('dashboard-section', 'section-stats');
  checklistCard.classList.add('dashboard-section', 'section-checklist');

  // Set default active tab
  statsGrid.classList.add('active');

  // Create mobile tab container with 2 tabs: Stats and Tasks
  const tabContainer = document.createElement('div');
  tabContainer.className = 'dashboard-mobile-tabs';
  tabContainer.innerHTML = `
    <button class="db-tab active" data-sec="stats"><i class="fa-solid fa-chart-simple"></i>Stats</button>
    <button class="db-tab" data-sec="checklist"><i class="fa-solid fa-list-check"></i>Tasks</button>
  `;

  // Insert tabs before statsGrid
  statsGrid.parentNode.insertBefore(tabContainer, statsGrid);

  // Bind click handlers
  tabContainer.querySelectorAll('.db-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      tabContainer.querySelectorAll('.db-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      main.querySelectorAll('.dashboard-section').forEach(s => s.classList.remove('active'));

      const sec = btn.getAttribute('data-sec');
      if (sec === 'stats') statsGrid.classList.add('active');
      if (sec === 'checklist') checklistCard.classList.add('active');
    });
  });
}

// ── Gym Layout Mobile Tabs ────────────────────────────────────
function initGymMobileTabs() {
  const pathname = window.location.pathname.replace(/\/$/, '') || '/';
  if (pathname !== '/gym' && pathname !== '/gym.html') return;

  const gymLayout = document.querySelector('.gym-layout');
  if (!gymLayout) return;

  const children = Array.from(gymLayout.children);
  if (children.length < 2) return;

  const formCard = children[0];
  const historyCard = children[1];

  formCard.classList.add('dashboard-section', 'section-log');
  historyCard.classList.add('dashboard-section', 'section-history');

  // Set default active section
  formCard.classList.add('active');

  // Create mobile tab container
  const tabContainer = document.createElement('div');
  tabContainer.className = 'dashboard-mobile-tabs';
  tabContainer.innerHTML = `
    <button class="db-tab active" data-sec="log"><i class="fa-solid fa-plus-circle"></i>Log Workout</button>
    <button class="db-tab" data-sec="history"><i class="fa-solid fa-clock-rotate-left"></i>History</button>
  `;

  // Insert tabs before gymLayout
  gymLayout.parentNode.insertBefore(tabContainer, gymLayout);

  // Bind click handlers
  tabContainer.querySelectorAll('.db-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      tabContainer.querySelectorAll('.db-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      gymLayout.querySelectorAll('.dashboard-section').forEach(s => s.classList.remove('active'));

      const sec = btn.getAttribute('data-sec');
      if (sec === 'log') formCard.classList.add('active');
      if (sec === 'history') historyCard.classList.add('active');
    });
  });
}

// ── Study Journal Mobile Tabs ─────────────────────────────────
function initJournalMobileTabs() {
  const pathname = window.location.pathname.replace(/\/$/, '') || '/';
  if (pathname !== '/journal' && pathname !== '/journal.html') return;

  const journalGrid = document.querySelector('.journal-grid');
  if (!journalGrid) return;

  const children = Array.from(journalGrid.children);
  if (children.length < 2) return;

  const formCard = children[0];
  const historyCard = children[1];

  formCard.classList.add('dashboard-section', 'section-log');
  historyCard.classList.add('dashboard-section', 'section-history');

  // Set default active section
  formCard.classList.add('active');

  // Create mobile tab container
  const tabContainer = document.createElement('div');
  tabContainer.className = 'dashboard-mobile-tabs';
  tabContainer.innerHTML = `
    <button class="db-tab active" data-sec="log"><i class="fa-solid fa-pen-to-square"></i>Log Entry</button>
    <button class="db-tab" data-sec="history"><i class="fa-solid fa-clock-rotate-left"></i>History</button>
  `;

  // Insert tabs before journalGrid
  journalGrid.parentNode.insertBefore(tabContainer, journalGrid);

  // Bind click handlers
  tabContainer.querySelectorAll('.db-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      tabContainer.querySelectorAll('.db-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      journalGrid.querySelectorAll('.dashboard-section').forEach(s => s.classList.remove('active'));

      const sec = btn.getAttribute('data-sec');
      if (sec === 'log') formCard.classList.add('active');
      if (sec === 'history') historyCard.classList.add('active');
    });
  });
}

function injectDesktopSidebarNav() {
  const nav = document.querySelector('.nav');
  if (!nav) return;
  const pathname = window.location.pathname.replace(/\/$/, '') || '/';

  // 0. Ensure Work Tracker is inserted right after Canvas LMS (/canvas)
  if (!nav.querySelector('a[href="/work-tracker"]')) {
    const canvasLi = nav.querySelector('a[href="/canvas"]')?.closest('li');
    const li = document.createElement('li');
    const activeClass = (pathname === '/work-tracker' || pathname === '/work_tracker' || pathname === '/work_tracker.html') ? 'class="active"' : '';
    li.innerHTML = `<a href="/work-tracker" ${activeClass}><i class="fa-solid fa-briefcase" style="color:var(--indigo)"></i><span>Work Tracker</span><span class="nav-badge" style="background:rgba(99,102,241,0.2);color:#818cf8;border-color:rgba(99,102,241,0.3)">XP</span></a>`;
    if (canvasLi && canvasLi.nextSibling) {
      nav.insertBefore(li, canvasLi.nextSibling);
    } else {
      nav.appendChild(li);
    }
  }

  // 1. Ensure Gym Pro is inserted right after Study Path (/syllabus)
  if (!nav.querySelector('a[href="/gym-pro"]')) {
    const syllabusLi = nav.querySelector('a[href="/syllabus"]')?.closest('li');
    const li = document.createElement('li');
    const activeClass = (pathname === '/gym-pro' || pathname === '/gym_pro' || pathname === '/gym-pro.html' || pathname === '/gym_pro.html') ? 'class="active"' : '';
    li.innerHTML = `<a href="/gym-pro" ${activeClass}><i class="fa-solid fa-bolt" style="color:var(--amber)"></i><span>Gym Pro</span><span class="nav-badge" style="background:rgba(245,158,11,0.2);color:#f59e0b;border-color:rgba(245,158,11,0.3)">PRO</span></a>`;
    if (syllabusLi && syllabusLi.nextSibling) {
      nav.insertBefore(li, syllabusLi.nextSibling);
    } else {
      nav.appendChild(li);
    }
  }

  // 2. Ensure Gym Tracker is inserted right after Activity Logs (/logs)
  if (!nav.querySelector('a[href="/gym"]')) {
    const logsLi = nav.querySelector('a[href="/logs"]')?.closest('li');
    const li = document.createElement('li');
    const activeClass = (pathname === '/gym' || pathname === '/gym.html') ? 'class="active"' : '';
    li.innerHTML = `<a href="/gym" ${activeClass}><i class="fa-solid fa-dumbbell"></i><span>Gym Tracker</span></a>`;
    if (logsLi && logsLi.nextSibling) {
      nav.insertBefore(li, logsLi.nextSibling);
    } else {
      nav.appendChild(li);
    }
  }

  // 3. Ensure System OS is inserted at the end
  if (!nav.querySelector('a[href="/system"]')) {
    const li = document.createElement('li');
    const activeClass = (pathname === '/system' || pathname === '/system.html') ? 'class="active"' : '';
    li.innerHTML = `<a href="/system" ${activeClass}><i class="fa-solid fa-gamepad" style="color:var(--rose)"></i><span>System OS</span><span class="nav-badge" style="background:rgba(244,63,94,0.2);color:#fda4af;border-color:rgba(244,63,94,0.3)">SOLO</span></a>`;
    nav.appendChild(li);
  }
}

async function loadMiniStats() {
  try {
    injectFloatingStatsBar();
    injectMobileNavigation();
    injectDesktopSidebarNav();
    initDashboardMobileTabs();
    initGymMobileTabs();
    initJournalMobileTabs();
    renderVoiceControls();
    startVoiceDaemonTimer();

    const r = await apiFetch('/stats');
    if (!r.ok) return;
    const d = await r.json();
    const setEl = (id, val) => { const e = document.getElementById(id); if (e) e.textContent = val; };
    setEl('hdr-lvl', d.level);
    setEl('hdr-xp', d.xp);
    setEl('hdr-energy', Math.round(d.energy) + '%');
    setEl('hdr-streak', d.streak_days + 'd');

    const syncIcon = document.getElementById('sync-icon');
    const syncText = document.getElementById('sync-text');
    if (syncIcon && syncText) {
      if (d.neon_online) {
        syncIcon.className = 'fa-solid fa-circle';
        syncIcon.style.color = 'var(--green)';
        syncText.textContent = 'Online';
      } else {
        syncIcon.className = 'fa-solid fa-triangle-exclamation';
        syncIcon.style.color = 'var(--amber)';
        syncText.textContent = 'Offline';
      }
    }

    if (d.level) {
      checkLevelUpEvent(d.level);
    }
  } catch (_) { }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadMiniStats);
} else {
  loadMiniStats();
}

// Register PWA Service Worker
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").then((reg) => {
      console.log("Service Worker registered successfully:", reg.scope);
    }).catch((err) => {
      console.error("Service Worker registration failed:", err);
    });
  });
}
