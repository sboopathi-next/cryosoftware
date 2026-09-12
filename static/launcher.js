/**
 * launcher.js — Antigravity OS Minimalist Home Launcher & App Blocker Controller
 * Interfaces with native Android WebBridgeInterface when running inside the APK container.
 */

(function () {
  'use strict';

  const isNative = typeof window.AntigravityNative !== 'undefined';
  let installedApps = [];
  let blockedApps = [];
  let favoritePackages = JSON.parse(localStorage.getItem('antigravity_fav_apps') || '[]');

  // Default favorites if empty
  if (favoritePackages.length === 0) {
    favoritePackages = ['com.google.android.dialer', 'com.google.android.apps.messaging', 'com.android.chrome', 'com.whatsapp'];
  }

  // ─── 1. Initialization ───────────────────────────────────────────────────
  function initLauncher() {
    createLauncherUIElements();
    loadApps();
    checkPermissions();

    // Register global callbacks invoked by Android Activity
    window.onAppIntercepted = handleAppIntercepted;
    window.onHomePressed = handleHomePressed;
    window.onLauncherResumed = handleLauncherResumed;

    // Attach bottom dock quick-launch trigger
    setupDockButton();
  }

  // ─── 2. Fetch & Sync Apps ────────────────────────────────────────────────
  function loadApps() {
    if (!isNative) {
      // Mock data for browser testing
      installedApps = [
        { name: "Phone", packageName: "com.google.android.dialer", isSystem: true },
        { name: "Messages", packageName: "com.google.android.apps.messaging", isSystem: true },
        { name: "Chrome", packageName: "com.android.chrome", isSystem: false },
        { name: "WhatsApp", packageName: "com.whatsapp", isSystem: false },
        { name: "Instagram", packageName: "com.instagram.android", isSystem: false },
        { name: "YouTube", packageName: "com.google.android.youtube", isSystem: false },
        { name: "Settings", packageName: "com.android.settings", isSystem: true }
      ];
      blockedApps = ["com.instagram.android", "com.google.android.youtube"];
      renderAppDrawer();
      renderFavorites();
      return;
    }

    try {
      const appsJson = window.AntigravityNative.getInstalledApps();
      installedApps = JSON.parse(appsJson || '[]');

      const blockedJson = window.AntigravityNative.getBlockedApps();
      blockedApps = JSON.parse(blockedJson || '[]');

      renderAppDrawer();
      renderFavorites();
    } catch (e) {
      console.error('[Antigravity Launcher] Failed to load apps:', e);
    }
  }

  function checkPermissions() {
    if (!isNative) return;
    try {
      const statusJson = window.AntigravityNative.getPermissionStatus();
      const status = JSON.parse(statusJson || '{}');
      updatePermissionPills(status);
    } catch (e) {
      console.error('[Antigravity Launcher] Failed to check permissions:', e);
    }
  }

  // ─── 3. Launch App with Mindful Friction ─────────────────────────────────
  function launchApp(packageName, appName) {
    if (isNative) {
      window.AntigravityNative.triggerHaptic(20);
    }

    const isBlocked = blockedApps.includes(packageName);

    if (isBlocked) {
      showFrictionIntervention(packageName, appName || packageName);
    } else {
      executeAppLaunch(packageName);
    }
  }

  function executeAppLaunch(packageName) {
    if (isNative) {
      window.AntigravityNative.launchApp(packageName);
    } else {
      console.log(`[Antigravity Native Simulation] Launching: ${packageName}`);
      alert(`Simulation: Launching ${packageName}`);
    }
    closeAppDrawer();
  }

  // ─── 4. Friction / Mindful Pause Modal ───────────────────────────────────
  function showFrictionIntervention(packageName, appName) {
    const modal = document.getElementById('friction-modal');
    if (!modal) return;

    const titleEl = document.getElementById('friction-title');
    const msgEl = document.getElementById('friction-msg');
    const countdownEl = document.getElementById('friction-countdown');
    const btnProceed = document.getElementById('friction-btn-proceed');

    titleEl.textContent = `Mindful Pause: ${appName}`;
    msgEl.textContent = 'Take 3 deep breaths. Is opening this application aligned with your highest priority quest today?';
    
    let secondsLeft = 10;
    countdownEl.textContent = `Unlocking in ${secondsLeft}s...`;
    btnProceed.disabled = true;
    btnProceed.classList.add('opacity-40', 'cursor-not-allowed');

    modal.classList.remove('hidden');
    modal.classList.add('flex');

    if (window._frictionInterval) clearInterval(window._frictionInterval);
    window._frictionInterval = setInterval(() => {
      secondsLeft--;
      if (secondsLeft > 0) {
        countdownEl.textContent = `Unlocking in ${secondsLeft}s...`;
      } else {
        clearInterval(window._frictionInterval);
        countdownEl.textContent = 'Intention confirmed.';
        btnProceed.disabled = false;
        btnProceed.classList.remove('opacity-40', 'cursor-not-allowed');
      }
    }, 1000);

    btnProceed.onclick = () => {
      clearInterval(window._frictionInterval);
      modal.classList.add('hidden');
      modal.classList.remove('flex');
      executeAppLaunch(packageName);
    };
  }

  function handleAppIntercepted(packageName, reason) {
    console.log(`[Focus Intercepted] Blocked app attempt: ${packageName} (${reason})`);
    let appName = packageName;
    const found = installedApps.find(a => a.packageName === packageName);
    if (found) appName = found.name;

    showFrictionIntervention(packageName, appName);
  }

  function handleHomePressed() {
    closeAppDrawer();
    closeLauncherSettings();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function handleLauncherResumed() {
    checkPermissions();
  }

  // ─── 5. UI Builder: Minimalist Drawer & Modals ───────────────────────────
  function createLauncherUIElements() {
    if (document.getElementById('minimal-app-drawer')) return;

    const drawerHtml = `
      <!-- Minimalist App Drawer (Swipe Up / Fullscreen Overlay) -->
      <div id="minimal-app-drawer" class="fixed inset-0 z-50 bg-[#07090e]/98 backdrop-blur-2xl hidden flex-col transition-all duration-300">
        <div class="px-6 pt-12 pb-4 border-b border-slate-800/60 flex items-center justify-between">
          <div class="flex items-center gap-3 w-full max-w-md">
            <i class="fa-solid fa-magnifying-glass text-slate-500 text-sm"></i>
            <input id="drawer-search-input" type="text" placeholder="Type app name..." 
              class="bg-transparent border-none text-slate-100 placeholder-slate-500 text-lg font-mono focus:outline-none focus:ring-0 w-full"
              autocomplete="off" autocorrect="off" spellcheck="false" />
          </div>
          <button id="drawer-btn-close" class="text-slate-400 hover:text-white p-2 rounded-lg bg-slate-800/40 border border-slate-700/40">
            <i class="fa-solid fa-xmark text-lg"></i>
          </button>
        </div>

        <!-- Quick Favorites Row -->
        <div id="drawer-favorites-container" class="px-6 py-3 border-b border-slate-800/40 flex items-center gap-3 overflow-x-auto no-scrollbar">
          <!-- Filled by renderFavorites() -->
        </div>

        <!-- App List Alphabetical -->
        <div id="drawer-app-list" class="flex-1 overflow-y-auto px-6 py-4 divide-y divide-slate-800/30 space-y-1">
          <!-- Populated dynamically -->
        </div>
      </div>

      <!-- Mindful Friction Modal -->
      <div id="friction-modal" class="fixed inset-0 z-50 bg-black/90 backdrop-blur-xl hidden items-center justify-center p-6">
        <div class="bg-[#0e1320] border border-cyan-500/30 rounded-2xl p-6 max-w-sm w-full text-center shadow-2xl space-y-5">
          <div class="w-16 h-16 rounded-full bg-cyan-950/80 border border-cyan-500/50 flex items-center justify-center mx-auto text-cyan-400 text-2xl animate-pulse">
            <i class="fa-solid fa-shield-halved"></i>
          </div>
          <div>
            <h3 id="friction-title" class="text-lg font-bold text-white">Mindful Pause</h3>
            <p id="friction-msg" class="text-xs text-slate-400 mt-2 leading-relaxed">Take a deep breath before opening.</p>
          </div>
          <div id="friction-countdown" class="text-sm font-mono font-semibold text-cyan-400 bg-cyan-950/40 py-2 rounded-xl border border-cyan-800/30">
            Unlocking in 10s...
          </div>
          <div class="flex gap-3">
            <button id="friction-btn-back" class="flex-1 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold">
              Back to Mission
            </button>
            <button id="friction-btn-proceed" class="flex-1 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-black text-xs font-bold transition-all">
              Proceed Anyway
            </button>
          </div>
        </div>
      </div>

      <!-- Launcher System Permissions Modal -->
      <div id="launcher-settings-modal" class="fixed inset-0 z-50 bg-black/85 backdrop-blur-md hidden items-center justify-center p-4">
        <div class="bg-[#0e1320] border border-slate-700/60 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto">
          <div class="flex justify-between items-center border-b border-slate-800 pb-3">
            <div class="flex items-center gap-2.5">
              <i class="fa-solid fa-mobile-screen-button text-cyan-400"></i>
              <h3 class="font-bold text-white text-base">Antigravity OS Launcher Settings</h3>
            </div>
            <button id="launcher-settings-close" class="text-slate-400 hover:text-white p-1.5"><i class="fa-solid fa-xmark text-lg"></i></button>
          </div>

          <div class="space-y-3 text-xs">
            <!-- 1. Default Home Launcher -->
            <div class="p-3.5 bg-slate-900/80 rounded-xl border border-slate-800 flex justify-between items-center">
              <div>
                <p class="font-semibold text-slate-200">Default Home Launcher</p>
                <p class="text-[11px] text-slate-400 mt-0.5">Makes this dashboard your phone's main home screen.</p>
              </div>
              <button id="btn-perm-home" class="px-3 py-1.5 rounded-lg bg-cyan-950 text-cyan-300 border border-cyan-500/40 font-mono text-[11px]">Set Default</button>
            </div>

            <!-- 2. Usage Stats (Screen Time) -->
            <div class="p-3.5 bg-slate-900/80 rounded-xl border border-slate-800 flex justify-between items-center">
              <div>
                <p class="font-semibold text-slate-200">Usage Access (Screen Time)</p>
                <p class="text-[11px] text-slate-400 mt-0.5">Allows tracking screen time & app addiction.</p>
              </div>
              <button id="btn-perm-usage" class="px-3 py-1.5 rounded-lg bg-cyan-950 text-cyan-300 border border-cyan-500/40 font-mono text-[11px]">Enable</button>
            </div>

            <!-- 3. Accessibility Service (Focus Blocker) -->
            <div class="p-3.5 bg-slate-900/80 rounded-xl border border-slate-800 flex justify-between items-center">
              <div>
                <p class="font-semibold text-slate-200">Focus Governor (Accessibility)</p>
                <p class="text-[11px] text-slate-400 mt-0.5">Intercepts distracting apps in real-time.</p>
              </div>
              <button id="btn-perm-access" class="px-3 py-1.5 rounded-lg bg-cyan-950 text-cyan-300 border border-cyan-500/40 font-mono text-[11px]">Enable</button>
            </div>

            <!-- 4. Notification Listener -->
            <div class="p-3.5 bg-slate-900/80 rounded-xl border border-slate-800 flex justify-between items-center">
              <div>
                <p class="font-semibold text-slate-200">Notification Gatekeeper</p>
                <p class="text-[11px] text-slate-400 mt-0.5">Mutes social pings during deep work hours.</p>
              </div>
              <button id="btn-perm-notif" class="px-3 py-1.5 rounded-lg bg-cyan-950 text-cyan-300 border border-cyan-500/40 font-mono text-[11px]">Enable</button>
            </div>

            <!-- 5. Overlay Permission -->
            <div class="p-3.5 bg-slate-900/80 rounded-xl border border-slate-800 flex justify-between items-center">
              <div>
                <p class="font-semibold text-slate-200">Draw Over Other Apps</p>
                <p class="text-[11px] text-slate-400 mt-0.5">Required for lockscreens and friction timers.</p>
              </div>
              <button id="btn-perm-overlay" class="px-3 py-1.5 rounded-lg bg-cyan-950 text-cyan-300 border border-cyan-500/40 font-mono text-[11px]">Enable</button>
            </div>
          </div>

          <!-- Distraction Blocklist Manager -->
          <div class="border-t border-slate-800 pt-4">
            <h4 class="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">Distraction App Blocklist</h4>
            <div id="blocklist-tags" class="flex flex-wrap gap-2 text-[11px] font-mono">
              <!-- Rendered dynamically -->
            </div>
          </div>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML('beforeend', drawerHtml);

    // Event Bindings
    document.getElementById('drawer-btn-close').onclick = closeAppDrawer;
    document.getElementById('friction-btn-back').onclick = () => {
      document.getElementById('friction-modal').classList.add('hidden');
      document.getElementById('friction-modal').classList.remove('flex');
    };
    document.getElementById('launcher-settings-close').onclick = closeLauncherSettings;

    // Search input instant fuzzy filter
    const searchInput = document.getElementById('drawer-search-input');
    searchInput.addEventListener('input', (e) => {
      renderAppDrawer(e.target.value);
    });

    // Permission button handlers
    setupPermissionButtons();
  }

  function setupPermissionButtons() {
    const btnHome = document.getElementById('btn-perm-home');
    const btnUsage = document.getElementById('btn-perm-usage');
    const btnAccess = document.getElementById('btn-perm-access');
    const btnNotif = document.getElementById('btn-perm-notif');
    const btnOverlay = document.getElementById('btn-perm-overlay');

    if (btnHome) btnHome.onclick = () => isNative && window.AntigravityNative.openDefaultLauncherSettings();
    if (btnUsage) btnUsage.onclick = () => isNative && window.AntigravityNative.openUsageSettings();
    if (btnAccess) btnAccess.onclick = () => isNative && window.AntigravityNative.openAccessibilitySettings();
    if (btnNotif) btnNotif.onclick = () => isNative && window.AntigravityNative.openNotificationListenerSettings();
    if (btnOverlay) btnOverlay.onclick = () => isNative && window.AntigravityNative.openOverlaySettings();
  }

  function updatePermissionPills(status) {
    const updateBtn = (id, active) => {
      const el = document.getElementById(id);
      if (!el) return;
      if (active) {
        el.textContent = 'Active ✓';
        el.className = 'px-3 py-1.5 rounded-lg bg-emerald-950 text-emerald-400 border border-emerald-500/40 font-mono text-[11px] font-semibold';
      } else {
        el.textContent = 'Enable';
        el.className = 'px-3 py-1.5 rounded-lg bg-cyan-950 text-cyan-300 border border-cyan-500/40 font-mono text-[11px]';
      }
    };

    updateBtn('btn-perm-home', status.isDefaultLauncher);
    updateBtn('btn-perm-usage', status.hasUsageAccess);
    updateBtn('btn-perm-access', status.hasAccessibilityPermission);
    updateBtn('btn-perm-notif', status.hasNotificationListenerPermission);
    updateBtn('btn-perm-overlay', status.hasOverlayPermission);
  }

  // ─── 6. App List & Favorites Rendering ───────────────────────────────────
  function renderAppDrawer(query = '') {
    const container = document.getElementById('drawer-app-list');
    if (!container) return;

    const filtered = installedApps.filter(app =>
      app.name.toLowerCase().includes(query.toLowerCase()) ||
      app.packageName.toLowerCase().includes(query.toLowerCase())
    );

    if (filtered.length === 0) {
      container.innerHTML = `<div class="text-center py-12 text-slate-500 font-mono text-sm">No apps found for "${query}"</div>`;
      return;
    }

    container.innerHTML = filtered.map(app => {
      const isBlocked = blockedApps.includes(app.packageName);
      const isFav = favoritePackages.includes(app.packageName);

      return `
        <div class="py-3 px-2 flex items-center justify-between hover:bg-slate-800/40 rounded-xl cursor-pointer transition-colors" data-pkg="${app.packageName}">
          <div class="flex items-center gap-3.5 flex-1 app-launch-trigger" data-pkg="${app.packageName}" data-name="${app.name}">
            <div class="w-8 h-8 rounded-lg bg-slate-800/80 border border-slate-700/50 flex items-center justify-center font-mono text-xs font-bold text-slate-300">
              ${app.name.charAt(0).toUpperCase()}
            </div>
            <div>
              <p class="text-sm font-medium text-slate-100 ${isBlocked ? 'text-rose-400' : ''}">${app.name}</p>
              <p class="text-[10px] font-mono text-slate-500">${app.packageName}</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            ${isBlocked ? '<span class="px-2 py-0.5 rounded bg-rose-950/60 text-rose-400 border border-rose-800/40 text-[10px] font-mono">Restricted</span>' : ''}
            <button class="toggle-fav-btn p-1.5 text-slate-500 hover:text-amber-400 text-xs" data-pkg="${app.packageName}">
              <i class="${isFav ? 'fa-solid text-amber-400' : 'fa-regular'} fa-star"></i>
            </button>
            <button class="toggle-block-btn p-1.5 text-slate-500 hover:text-rose-400 text-xs" data-pkg="${app.packageName}">
              <i class="fa-solid fa-ban"></i>
            </button>
          </div>
        </div>
      `;
    }).join('');

    // Attach click triggers
    container.querySelectorAll('.app-launch-trigger').forEach(el => {
      el.onclick = () => {
        launchApp(el.getAttribute('data-pkg'), el.getAttribute('data-name'));
      };
    });

    container.querySelectorAll('.toggle-fav-btn').forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        toggleFavorite(btn.getAttribute('data-pkg'));
      };
    });

    container.querySelectorAll('.toggle-block-btn').forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        toggleBlock(btn.getAttribute('data-pkg'));
      };
    });

    renderBlocklistTags();
  }

  function renderFavorites() {
    const container = document.getElementById('drawer-favorites-container');
    if (!container) return;

    const favApps = installedApps.filter(a => favoritePackages.includes(a.packageName));

    if (favApps.length === 0) {
      container.innerHTML = `<span class="text-[11px] font-mono text-slate-500">Star apps below to pin to quick launch</span>`;
      return;
    }

    container.innerHTML = favApps.map(app => `
      <button class="fav-quick-btn px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700/60 text-slate-200 text-xs font-mono flex items-center gap-2 hover:border-cyan-500/50" data-pkg="${app.packageName}" data-name="${app.name}">
        <span>${app.name}</span>
      </button>
    `).join('');

    container.querySelectorAll('.fav-quick-btn').forEach(btn => {
      btn.onclick = () => {
        launchApp(btn.getAttribute('data-pkg'), btn.getAttribute('data-name'));
      };
    });
  }

  function renderBlocklistTags() {
    const container = document.getElementById('blocklist-tags');
    if (!container) return;

    if (blockedApps.length === 0) {
      container.innerHTML = '<span class="text-slate-500">No apps currently restricted.</span>';
      return;
    }

    container.innerHTML = blockedApps.map(pkg => `
      <span class="px-2.5 py-1 rounded-lg bg-rose-950/80 text-rose-300 border border-rose-800/50 flex items-center gap-1.5">
        <span>${pkg.split('.').pop()}</span>
        <button class="remove-block-tag text-rose-400 hover:text-white" data-pkg="${pkg}">×</button>
      </span>
    `).join('');

    container.querySelectorAll('.remove-block-tag').forEach(btn => {
      btn.onclick = () => toggleBlock(btn.getAttribute('data-pkg'));
    });
  }

  function toggleFavorite(pkg) {
    if (favoritePackages.includes(pkg)) {
      favoritePackages = favoritePackages.filter(p => p !== pkg);
    } else {
      favoritePackages.push(pkg);
    }
    localStorage.setItem('antigravity_fav_apps', JSON.stringify(favoritePackages));
    renderAppDrawer(document.getElementById('drawer-search-input')?.value || '');
    renderFavorites();
  }

  function toggleBlock(pkg) {
    if (blockedApps.includes(pkg)) {
      blockedApps = blockedApps.filter(p => p !== pkg);
    } else {
      blockedApps.push(pkg);
    }

    if (isNative) {
      window.AntigravityNative.setBlockedApps(JSON.stringify(blockedApps));
    }

    renderAppDrawer(document.getElementById('drawer-search-input')?.value || '');
  }

  // ─── 7. Dock & Modal Visibility Handlers ─────────────────────────────────
  function setupDockButton() {
    // Inject Launcher Quick Bar if not exists on mobile view
    let mobileNav = document.getElementById('mobile-bottom-dock');
    if (!mobileNav) {
      mobileNav = document.createElement('div');
      mobileNav.id = 'mobile-bottom-dock';
      mobileNav.className = 'fixed bottom-4 left-1/2 transform -translate-x-1/2 z-40 bg-[#0e1320]/90 backdrop-blur-xl px-5 py-2.5 rounded-full border border-slate-700/60 shadow-2xl flex items-center gap-6 text-slate-300 text-sm';
      mobileNav.innerHTML = `
        <button id="dock-btn-home" class="hover:text-cyan-400 transition-colors flex flex-col items-center gap-0.5">
          <i class="fa-solid fa-house text-base"></i>
          <span class="text-[9px] font-mono">HOME</span>
        </button>
        <button id="dock-btn-drawer" class="px-4 py-1.5 rounded-full bg-cyan-600 hover:bg-cyan-500 text-black font-bold flex items-center gap-1.5 transition-transform active:scale-95 shadow-lg shadow-cyan-500/20">
          <i class="fa-solid fa-grid-2 text-xs"></i>
          <span class="text-xs font-mono">APPS</span>
        </button>
        <button id="dock-btn-settings" class="hover:text-cyan-400 transition-colors flex flex-col items-center gap-0.5">
          <i class="fa-solid fa-sliders text-base"></i>
          <span class="text-[9px] font-mono">SETTINGS</span>
        </button>
      `;
      document.body.appendChild(mobileNav);

      document.getElementById('dock-btn-home').onclick = () => window.scrollTo({ top: 0, behavior: 'smooth' });
      document.getElementById('dock-btn-drawer').onclick = openAppDrawer;
      document.getElementById('dock-btn-settings').onclick = openLauncherSettings;
    }
  }

  function openAppDrawer() {
    const drawer = document.getElementById('minimal-app-drawer');
    if (!drawer) return;
    drawer.classList.remove('hidden');
    drawer.classList.add('flex');
    loadApps();
    const input = document.getElementById('drawer-search-input');
    if (input) {
      input.value = '';
      input.focus();
    }
  }

  function closeAppDrawer() {
    const drawer = document.getElementById('minimal-app-drawer');
    if (!drawer) return;
    drawer.classList.add('hidden');
    drawer.classList.remove('flex');
  }

  function openLauncherSettings() {
    const modal = document.getElementById('launcher-settings-modal');
    if (!modal) return;
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    checkPermissions();
  }

  function closeLauncherSettings() {
    const modal = document.getElementById('launcher-settings-modal');
    if (!modal) return;
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }

  // Export interface globally
  window.AntigravityLauncher = {
    openDrawer: openAppDrawer,
    closeDrawer: closeAppDrawer,
    openSettings: openLauncherSettings,
    launchApp: launchApp,
    isNative: isNative
  };

  // Auto-init on DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initLauncher);
  } else {
    initLauncher();
  }
})();
