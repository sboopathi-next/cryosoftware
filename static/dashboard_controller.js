/**
 * dashboard_controller.js — Antigravity Mission Control Dashboard Controller
 * Manages live telemetry hydration, 8s polling, energy tier ring, 10 accountability tasks,
 * side dock controls, and modal interactions.
 */

(function () {
  'use strict';

  // State cache
  let currentStats = null;
  let currentEnergy = null;
  let currentFitness = null;

  // DOM Helper
  const $ = (id) => document.getElementById(id);

  // Toast notifier fallback
  function notify(msg, type = 'info') {
    if (window.toast) {
      window.toast(msg, type);
    } else {
      console.log(`[Dashboard Notification] (${type})`, msg);
      // Subtle float toast
      let toastEl = document.getElementById('dashboard-toast');
      if (!toastEl) {
        toastEl = document.createElement('div');
        toastEl.id = 'dashboard-toast';
        toastEl.className = 'fixed top-4 right-4 z-50 px-4 py-2.5 rounded-xl shadow-2xl text-xs font-semibold backdrop-blur-md border transition-all duration-300 transform translate-y-0 opacity-100';
        document.body.appendChild(toastEl);
      }
      toastEl.style.background = type === 'err' ? 'rgba(239, 68, 68, 0.9)' : 'rgba(16, 185, 129, 0.9)';
      toastEl.style.color = '#ffffff';
      toastEl.style.borderColor = type === 'err' ? '#f87171' : '#34d399';
      toastEl.textContent = msg;
      toastEl.style.display = 'block';
      toastEl.style.opacity = '1';
      setTimeout(() => {
        toastEl.style.opacity = '0';
        setTimeout(() => { toastEl.style.display = 'none'; }, 300);
      }, 3500);
    }
  }

  // ─── 1. Telemetry Hydration & Polling ──────────────────────────────────────
  async function hydrateTelemetry() {
    try {
      const [statsRes, energyRes, fitRes] = await Promise.all([
        fetch('/stats').catch(() => fetch('/api/status')),
        fetch('/api/energy/state'),
        fetch('/api/fitness/summary')
      ]);

      if (statsRes && statsRes.ok) {
        currentStats = await statsRes.json();
        renderStatsUI(currentStats);
      }

      if (energyRes && energyRes.ok) {
        currentEnergy = await energyRes.json();
        renderEnergyUI(currentEnergy);
      }

      if (fitRes && fitRes.ok) {
        currentFitness = await fitRes.json();
        renderFitnessUI(currentFitness);
      }
    } catch (e) {
      console.warn('[Dashboard Hydration Warning]', e);
    }
  }

  // ─── 2. Stats & Attributes Renderer ───────────────────────────────────────
  function renderStatsUI(data) {
    if (!data) return;

    if ($('level-val')) $('level-val').textContent = data.level || 7;
    if ($('tier-badge')) $('tier-badge').textContent = `Tier Level ${data.level || 7}`;
    if ($('xp-val')) $('xp-val').textContent = data.xp || 0;
    if ($('xp-max')) $('xp-max').textContent = `/ ${data.xp_required || 2000}`;

    if ($('xp-progress-bar') && data.xp_required) {
      const pct = Math.min(100, Math.max(0, (data.xp / data.xp_required) * 100));
      $('xp-progress-bar').style.width = `${pct.toFixed(1)}%`;
    }

    if ($('streak-val')) $('streak-val').textContent = `${data.streak_days || 0} day streak`;

    // Attributes
    const attrs = data.attributes || {};
    if ($('attr-str')) $('attr-str').textContent = attrs.STR ?? 10;
    if ($('attr-int')) $('attr-int').textContent = attrs.INT ?? 10;
    if ($('attr-agi')) $('attr-agi').textContent = attrs.AGI ?? 10;
    if ($('attr-wil')) $('attr-wil').textContent = attrs.WIL ?? 10;
    if ($('attr-hrt')) $('attr-hrt').textContent = `${attrs.HRT ?? 72} bpm`;
    if ($('attr-stc')) $('attr-stc').textContent = attrs.STC ?? 10;

    // Daily Checklist Checkmark Updates
    updateChecklistItem('chk-study', data.study_completed);
    updateChecklistItem('chk-leetcode', data.leetcode_completed);
    updateChecklistItem('chk-gym', data.gym_completed);
    updateChecklistItem('chk-english', data.english_completed);
    updateChecklistItem('chk-cooking', data.cooking_completed);
    updateChecklistItem('chk-nopmo', data.nopmo_completed);
    updateChecklistItem('chk-reading', data.reading_completed, data.reading_book !== 'None' ? `Book: ${data.reading_book}` : null);
    updateChecklistItem('chk-fit', data.health_completed || data.walk_completed);
    updateChecklistItem('chk-meditation', data.meditation_completed);
    updateChecklistItem('chk-semester', data.canvas_semester_completed);
  }

  function updateChecklistItem(elementId, isCompleted, subtitleOverride) {
    const el = $(elementId);
    if (!el) return;

    const box = el.querySelector('.chk-box');
    const icon = el.querySelector('.chk-icon');
    const sub = el.querySelector('.chk-sub');

    if (isCompleted) {
      el.classList.remove('opacity-70', 'border-slate-800');
      el.classList.add('border-indigo-600/40', 'bg-[#111726]');
      if (box) {
        box.classList.remove('border-slate-600', 'bg-slate-900/50');
        box.classList.add('bg-indigo-600', 'border-indigo-500');
      }
      if (icon) {
        icon.classList.remove('opacity-0');
        icon.classList.add('opacity-100', 'text-white');
      }
    } else {
      el.classList.remove('border-indigo-600/40', 'bg-[#111726]');
      el.classList.add('opacity-80', 'border-slate-800', 'bg-[#101524]');
      if (box) {
        box.classList.remove('bg-indigo-600', 'border-indigo-500');
        box.classList.add('border-slate-600', 'bg-slate-900/50');
      }
      if (icon) {
        icon.classList.remove('opacity-100');
        icon.classList.add('opacity-0');
      }
    }

    if (subtitleOverride && sub) {
      sub.textContent = subtitleOverride;
    }
  }

  // ─── 3. Energy Engine UI Renderer ──────────────────────────────────────────
  function renderEnergyUI(data) {
    if (!data) return;

    const eVal = data.current_energy ?? 80;
    const tier = data.tier || 'NORMAL';
    const cap = data.max_task_capacity_minutes || 60;
    const deepBlocks = data.deep_work_blocks_used ?? 0;

    if ($('energy-pct-val')) $('energy-pct-val').textContent = `${Math.round(eVal)}%`;
    if ($('energy-mode-name')) $('energy-mode-name').textContent = `${tier} MODE`;
    if ($('energy-capacity-tag')) $('energy-capacity-tag').textContent = `${cap} min Max Cap`;
    if ($('deep-blocks-tag')) $('deep-blocks-tag').textContent = `${deepBlocks} / 3`;

    // Circular Gauge stroke dash offset (r=40 -> circumference = 251.2)
    const ring = $('energy-ring-circle');
    if (ring) {
      const strokeOffset = 251.2 - (251.2 * (Math.max(0, Math.min(100, eVal)) / 100.0));
      ring.setAttribute('stroke-dashoffset', strokeOffset.toFixed(1));

      // Color coding tier ring
      if (eVal >= 75) {
        ring.setAttribute('stroke', '#10b981'); // Emerald
      } else if (eVal >= 50) {
        ring.setAttribute('stroke', '#00e5ff'); // Cyan
      } else if (eVal >= 25) {
        ring.setAttribute('stroke', '#f59e0b'); // Amber
      } else {
        ring.setAttribute('stroke', '#ef4444'); // Crimson
      }
    }
  }

  // ─── 4. Fitness Telemetry UI Renderer ──────────────────────────────────────
  function renderFitnessUI(data) {
    if (!data) return;
    if ($('fit-steps-val')) $('fit-steps-val').textContent = (data.steps || 0).toLocaleString();
    if ($('fit-dist-val')) $('fit-dist-val').textContent = `${(data.distance_km || 0).toFixed(1)} km`;
    if ($('fit-sleep-val')) $('fit-sleep-val').textContent = `${data.sleep_hours || 7.5} hrs`;
    if ($('fit-mins-val')) $('fit-mins-val').textContent = `${data.active_minutes || 0} mins`;
  }

  // ─── 5. Accountability Tasks Handlers ─────────────────────────────────────
  function setupAccountabilityHandlers() {
    // 1. Study Target
    $('chk-study')?.addEventListener('click', async () => {
      try {
        const r = await fetch('/api/syllabus');
        if (r.ok) {
          window.location.href = '/syllabus';
        } else {
          notify('Redirecting to Study Path...', 'info');
          window.location.href = '/syllabus';
        }
      } catch (e) {
        window.location.href = '/syllabus';
      }
    });

    // 2. LeetCode Sync
    $('chk-leetcode')?.addEventListener('click', async () => {
      notify('Syncing LeetCode solved problems...', 'info');
      try {
        const r = await fetch('/api/leetcode/sync', { method: 'POST' });
        const d = await r.json();
        if (r.ok) {
          notify(d.message || 'LeetCode Synced!', 'ok');
          hydrateTelemetry();
        } else {
          notify(d.detail || 'LeetCode sync error', 'err');
        }
      } catch (e) {
        notify('Network error syncing LeetCode', 'err');
      }
    });

    // 3. Gym Target
    $('chk-gym')?.addEventListener('click', () => {
      openModal('gym-modal');
    });

    // 4. English Booster
    $('chk-english')?.addEventListener('click', async () => {
      try {
        const r = await fetch('/api/tasks/checklist/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ task_key: 'english_completed', value: !currentStats?.english_completed })
        });
        const d = await r.json();
        if (r.ok) {
          notify(d.message || 'English practice updated!', 'ok');
          hydrateTelemetry();
        }
      } catch (e) {
        notify('Error updating English booster', 'err');
      }
    });

    // 5. Cooking / Meal Prep
    $('chk-cooking')?.addEventListener('click', async () => {
      const nextVal = !(currentStats && currentStats.cooking_completed);
      updateChecklistItem('chk-cooking', nextVal);
      if (currentStats) currentStats.cooking_completed = nextVal;
      try {
        const r = await fetch('/api/tasks/checklist/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ task_key: 'cooking_completed', value: nextVal })
        });
        const d = await r.json();
        if (r.ok) {
          notify(d.message || (nextVal ? 'Meal prep logged! +10 XP' : 'Meal prep unmarked'), 'ok');
        } else {
          updateChecklistItem('chk-cooking', !nextVal);
        }
        hydrateTelemetry();
      } catch (e) {
        updateChecklistItem('chk-cooking', !nextVal);
        notify('Error toggling meal prep', 'err');
      }
    });

    // 6. NoPMO Discipline
    $('chk-nopmo')?.addEventListener('click', async () => {
      const nextVal = !(currentStats && currentStats.nopmo_completed);
      updateChecklistItem('chk-nopmo', nextVal);
      if (currentStats) currentStats.nopmo_completed = nextVal;
      try {
        const r = await fetch('/api/tasks/checklist/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ task_key: 'nopmo_completed', value: nextVal })
        });
        const d = await r.json();
        if (r.ok) {
          notify(d.message || (nextVal ? 'NoPMO Discipline logged! +15 XP, +1 WIL' : 'NoPMO unmarked'), 'ok');
        } else {
          updateChecklistItem('chk-nopmo', !nextVal);
        }
        hydrateTelemetry();
      } catch (e) {
        updateChecklistItem('chk-nopmo', !nextVal);
        notify('Error toggling NoPMO', 'err');
      }
    });

    // More Modules Pop-Up Button
    const bindMoreBtn = (btnId) => {
      const btn = $(btnId);
      if (btn) {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          openModal('more-modules-modal');
        });
      }
    };
    bindMoreBtn('btn-more-modules');
    bindMoreBtn('mobile-more-btn');
    bindMoreBtn('desktop-more-btn');

    // 7. Reading Book Modal Trigger
    $('chk-reading')?.addEventListener('click', () => {
      openReadingModal();
    });

    // 8. Sync Fit Button
    $('sync-fit-btn')?.addEventListener('click', async () => {
      notify('Connecting to Google Fit Cloud...', 'info');
      try {
        const r = await fetch('/api/health_sync/google_fit', { method: 'POST' });
        const d = await r.json();
        if (r.ok) {
          notify('Google Fit Cloud Synced!', 'ok');
          hydrateTelemetry();
        } else {
          notify(d.detail || 'Google Fit sync error', 'err');
        }
      } catch (e) {
        notify('Error triggering Fit sync', 'err');
      }
    });

    // 9. 5-Min Meditation
    $('chk-meditation')?.addEventListener('click', async () => {
      notify('Logging 5-Min Meditation...', 'info');
      try {
        const r = await fetch('/api/meditation/log', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ duration_minutes: 5 })
        });
        const d = await r.json();
        if (r.ok) {
          notify(d.message || 'Meditation logged! +20 XP, +2 STC, +1 WIL, +8 Energy', 'ok');
          hydrateTelemetry();
        }
      } catch (e) {
        notify('Error logging meditation', 'err');
      }
    });

    // 10. Semester ML Track
    $('chk-semester')?.addEventListener('click', async () => {
      notify('Syncing Semester ML Track...', 'info');
      try {
        const r = await fetch('/api/canvas/sync', { method: 'POST' });
        const d = await r.json();
        if (r.ok) {
          notify('Canvas LMS Sync Triggered!', 'ok');
          hydrateTelemetry();
        }
      } catch (e) {
        notify('Error triggering Canvas sync', 'err');
      }
    });
  }

  // ─── 6. Energy Side Dock & Modal Controls ──────────────────────────────────
  function setupSideDockControls() {
    // Energy Pool Readout
    $('dock-energy-btn')?.addEventListener('click', () => {
      openEnergyLedgerModal();
    });

    // Energy Task Sizer Calculator Modal
    $('dock-sizer-btn')?.addEventListener('click', () => {
      openModal('energy-sizer-modal');
    });

    // Quick Rest (+15 E)
    $('dock-rest-btn')?.addEventListener('click', async () => {
      notify('Taking 20-min Power Nap...', 'info');
      try {
        const r = await fetch('/api/energy/recover', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ recovery_type: 'POWER_NAP', units: 20 })
        });
        const d = await r.json();
        if (r.ok) {
          notify(`Power Nap Done! Energy restored to ${d.new_energy}%`, 'ok');
          hydrateTelemetry();
        }
      } catch (e) {
        notify('Error restoring energy', 'err');
      }
    });

    // Sleep Reset Rollover
    $('dock-sleep-btn')?.addEventListener('click', async () => {
      if (!confirm('Execute Sleep Reset Rollover (Reset Daily Energy based on Sleep)?')) return;
      notify('Executing Midnight Reset...', 'info');
      try {
        const r = await fetch('/api/energy/rollover', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sleep_hours: 8 })
        });
        const d = await r.json();
        if (r.ok) {
          notify(`Day Initialized! Morning Energy: ${d.morning_energy}% (${d.tier} MODE)`, 'ok');
          hydrateTelemetry();
        }
      } catch (e) {
        notify('Error executing sleep reset', 'err');
      }
    });

    // Energy Ledger History Modal Trigger
    $('dock-ledger-btn')?.addEventListener('click', () => {
      openEnergyLedgerModal();
    });

    // Dock Collapse Toggle
    $('dock-toggle-btn')?.addEventListener('click', () => {
      const container = $('dock-container');
      if (container) {
        container.classList.toggle('w-12');
        container.classList.toggle('w-10');
        container.classList.toggle('opacity-50');
      }
    });
  }

  // ─── 7. Modal Managers ────────────────────────────────────────────────────
  function openModal(id) {
    const modal = $(id);
    if (modal) {
      modal.classList.remove('hidden');
      modal.classList.add('flex');
    }
  }

  function closeModal(id) {
    const modal = $(id);
    if (modal) {
      modal.classList.add('hidden');
      modal.classList.remove('flex');
    }
  }

  window.closeModal = closeModal;

  async function openEnergyLedgerModal() {
    openModal('energy-ledger-modal');
    const container = $('energy-ledger-list');
    if (!container) return;

    container.innerHTML = '<div class="text-xs text-slate-400 p-3 text-center"><i class="fa-solid fa-spinner fa-spin mr-1"></i>Loading transaction history...</div>';
    try {
      const r = await fetch('/api/energy/ledger?limit=15');
      const rows = await r.json();
      if (!rows || !rows.length) {
        container.innerHTML = '<div class="text-xs text-slate-400 p-3 text-center">No energy transactions logged yet today.</div>';
        return;
      }

      container.innerHTML = rows.map(item => `
        <div class="bg-[#111726] border border-slate-800 rounded-xl p-2.5 flex items-center justify-between text-xs font-mono">
          <div>
            <div class="font-semibold ${item.transaction_type === 'DRAIN' ? 'text-rose-400' : 'text-emerald-400'}">
              ${item.transaction_type === 'DRAIN' ? '-' : '+'}${Math.round(item.magnitude)} E • ${item.category || 'Action'}
            </div>
            <div class="text-[10px] text-slate-500 mt-0.5">${new Date(item.logged_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
          </div>
          <div class="text-right">
            <span class="text-slate-300 font-bold">${Math.round(item.energy_before)}% → ${Math.round(item.energy_after)}%</span>
          </div>
        </div>
      `).join('');
    } catch (e) {
      container.innerHTML = '<div class="text-xs text-rose-400 p-3 text-center">Failed to load energy history.</div>';
    }
  }

  async function openReadingModal() {
    openModal('reading-modal');
    if ($('rd-title') && currentStats && currentStats.reading_book && currentStats.reading_book !== 'None') {
      if (!$('rd-title').value) {
        $('rd-title').value = currentStats.reading_book;
      }
    }
    const container = $('reading-recent-logs');
    if (!container) return;

    container.innerHTML = '<div class="text-xs text-slate-400 py-2 text-center"><i class="fa-solid fa-spinner fa-spin mr-1"></i>Loading reading logs...</div>';
    try {
      const r = await fetch('/api/reading/logs');
      const d = await r.json();
      const logs = (d && d.status === 'success' && d.logs) ? d.logs : (Array.isArray(d) ? d : []);
      if (!logs || !logs.length) {
        container.innerHTML = '<div class="text-xs text-slate-500 py-2 text-center">No reading logs recorded yet.</div>';
        return;
      }

      container.innerHTML = logs.slice(0, 10).map(item => `
        <div class="bg-[#111726] border border-slate-800 rounded-xl p-2 flex items-center justify-between text-xs cursor-pointer hover:border-amber-500/50 transition-colors" onclick="selectBookTitle('${(item.book_title || '').replace(/'/g, "\\'")}')">
          <div class="truncate mr-2">
            <div class="font-semibold text-amber-300 hover:underline truncate">${item.book_title || 'General Book'}</div>
            <div class="text-[10px] text-slate-400">Read p. ${item.page_from}–${item.page_to} (${item.pages_read || (item.page_to - item.page_from + 1)} pages)</div>
          </div>
          <div class="text-[10px] text-slate-500 whitespace-nowrap font-mono">
            ${item.timestamp ? item.timestamp.split(' ')[0] : (item.date || '')}
          </div>
        </div>
      `).join('');
    } catch (e) {
      container.innerHTML = '<div class="text-xs text-rose-400 py-2 text-center">Failed to load reading logs.</div>';
    }
  }

  window.selectBookTitle = function(title) {
    if ($('rd-title')) {
      $('rd-title').value = title;
      notify(`Selected book: "${title}"`, 'info');
    }
  };

  // Form Submit Handlers
  function setupFormSubmitHandlers() {
    // Reading Form
    $('reading-form')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const title = $('rd-title')?.value || 'General Book';
      const pageFrom = parseInt($('rd-from')?.value) || 1;
      const pageTo = parseInt($('rd-to')?.value) || 10;

      notify('Logging reading session...', 'info');
      try {
        const r = await fetch('/api/reading/log', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ book_title: title, page_from: pageFrom, page_to: pageTo })
        });
        const d = await r.json();
        if (r.ok) {
          notify(d.message || 'Reading logged!', 'ok');
          closeModal('reading-modal');
          hydrateTelemetry();
        } else {
          notify(d.detail || 'Error logging reading', 'err');
        }
      } catch (err) {
        notify('Network error logging reading', 'err');
      }
    });

    // Task Energy Calculator Engage Form
    $('sizer-form')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const category = $('sz-category')?.value || 'Machine_Learning';
      const duration = parseFloat($('sz-duration')?.value) || 30;
      const difficulty = parseInt($('sz-difficulty')?.value) || 5;

      notify('Engaging Protocol...', 'info');
      try {
        const r = await fetch('/api/energy/consume', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ category, duration_minutes: duration, difficulty })
        });
        const d = await r.json();
        if (r.ok && d.status === 'SUCCESS') {
          notify(`Engaged Protocol! -${d.energy_cost} E | +${d.xp_minted} XP`, 'ok');
          closeModal('energy-sizer-modal');
          hydrateTelemetry();
        } else {
          notify(d.detail || d.reason || 'Action rejected', 'err');
        }
      } catch (err) {
        notify('Network error engaging protocol', 'err');
      }
    });

    // Gym Logger Form
    $('gym-form')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const workout = $('gym-workout-title')?.value || 'Strength Routine';
      const duration = parseInt($('gym-workout-duration')?.value) || 45;

      notify('Logging Gym Workout...', 'info');
      try {
        const r = await fetch('/api/gympro/log_workout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ category: 'Gym_Pro', workout, duration_minutes: duration })
        });
        const d = await r.json();
        if (r.ok) {
          notify(d.message || 'Gym Workout Logged! +80 XP', 'ok');
          closeModal('gym-modal');
          hydrateTelemetry();
        } else {
          notify(d.detail || 'Error logging workout', 'err');
        }
      } catch (err) {
        notify('Error submitting workout', 'err');
      }
    });
  }

  // ─── 8. Initialization ────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    hydrateTelemetry();
    setupAccountabilityHandlers();
    setupSideDockControls();
    setupFormSubmitHandlers();

    // 8-second background polling
    setInterval(hydrateTelemetry, 8000);
  });

})();
