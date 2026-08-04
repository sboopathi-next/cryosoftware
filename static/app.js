// Global State
let currentState = null;

// DOM Selectors
const levelVal = document.getElementById("level-val");
const willpowerVal = document.getElementById("willpower-val");
const streakVal = document.getElementById("streak-val");
const xpBarFill = document.getElementById("xp-bar-fill");
const xpCurrent = document.getElementById("xp-current");
const xpRequired = document.getElementById("xp-required");

const energyBadge = document.getElementById("energy-badge");
const energyVal = document.getElementById("energy-val");

const studyHoursInput = document.getElementById("study-hours");
const studyLabel = document.getElementById("study-label");
const gymHoursInput = document.getElementById("gym-hours");
const gymLabel = document.getElementById("gym-label");
const dopamineRewardsInput = document.getElementById("dopamine-rewards");
const dopamineLabel = document.getElementById("dopamine-label");

const checkGym = document.getElementById("check-gym");
const checkCooking = document.getElementById("check-cooking");
const checkNopmo = document.getElementById("check-nopmo");

const coreQuestTitle = document.getElementById("core-quest-title");
const btnVerifyLeetcode = document.getElementById("btn-verify-leetcode");
const agilityQuestTitle = document.getElementById("agility-quest-title");
const btnCompleteAgility = document.getElementById("btn-complete-agility");

const lockScreen = document.getElementById("lockscreen");
const btnTogglePhysical = document.getElementById("btn-toggle-physical");
const btnToggleMath = document.getElementById("btn-toggle-math");
const formPhysical = document.getElementById("form-physical");
const formMath = document.getElementById("form-math");
const mathQuestion = document.getElementById("math-question");
const mathAnswer = document.getElementById("math-answer");
const btnSubmitPushups = document.getElementById("btn-submit-pushups");
const btnSubmitMath = document.getElementById("btn-submit-math");

const settingsModal = document.getElementById("settings-modal");
const btnSettings = document.getElementById("btn-settings");
const btnCloseSettings = document.getElementById("btn-close-settings");
const btnEmergencyBypass = document.getElementById("btn-emergency-bypass");

// SVG Ring Configuration (Circumference of r=68 is ~427.25)
const ringCircumference = 2 * Math.PI * 68;

// Slider listeners to show value updates live
studyHoursInput.addEventListener("input", (e) => { studyLabel.textContent = e.target.value; });
gymHoursInput.addEventListener("input", (e) => { gymLabel.textContent = e.target.value; });
dopamineRewardsInput.addEventListener("input", (e) => { dopamineLabel.textContent = e.target.value; });

// Toggle Lockscreen challenge views
btnTogglePhysical.addEventListener("click", () => {
  btnTogglePhysical.classList.add("active");
  btnToggleMath.classList.remove("active");
  formPhysical.style.display = "block";
  formMath.style.display = "none";
});

btnToggleMath.addEventListener("click", () => {
  btnToggleMath.classList.add("active");
  btnTogglePhysical.classList.remove("active");
  formMath.style.display = "block";
  formPhysical.style.display = "none";
  fetchMathChallenge();
});

// Fetch Status from server (with offline LocalStorage fallback)
async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    currentState = data;
    localStorage.setItem("antigravity_state", JSON.stringify(data));
    updateUI(data);
    if (typeof renderSyllabus === "function") {
      renderSyllabus();
    }
  } catch (err) {
    console.warn("Server offline, loading state from localStorage fallback:", err);
    const localData = localStorage.getItem("antigravity_state");
    if (localData) {
      currentState = JSON.parse(localData);
      updateUI(currentState);
      if (typeof renderSyllabus === "function") {
        renderSyllabus();
      }
    }
  }
}

// Update UI components with state values
function updateUI(state) {
  levelVal.textContent = state.level;
  willpowerVal.textContent = state.willpower || 10;
  streakVal.textContent = state.streak_days;
  
  // XP Calculation
  const reqXp = Math.floor(100 * Math.pow(state.level, 1.5));
  xpCurrent.textContent = state.xp;
  xpRequired.textContent = reqXp;
  const xpPercent = Math.min(100, (state.xp / reqXp) * 100);
  xpBarFill.style.width = `${xpPercent}%`;

  // Energy Capacity calculations
  const energy = state.energy;
  if (energyVal) {
    energyVal.textContent = energy;
  }
  
  if (energyBadge) {
    energyBadge.classList.remove("medium", "low");
    if (energy <= 20) {
      energyBadge.classList.add("low");
      energyBadge.childNodes[0].textContent = "🪫 ";
    } else if (energy <= 50) {
      energyBadge.classList.add("medium");
      energyBadge.childNodes[0].textContent = "🔋 ";
    } else {
      energyBadge.childNodes[0].textContent = "🔋 ";
    }
  }

  // Set checklists
  checkGym.checked = state.gym_completed || false;
  checkCooking.checked = state.cooking_completed || false;
  checkNopmo.checked = state.nopmo_completed || false;

  // Set Quest info
  coreQuestTitle.textContent = state.active_quests.core_skill;
  agilityQuestTitle.textContent = state.active_quests.agility_code;

  // Quest verify states
  if (state.completed_quests_today.includes("core_skill")) {
    btnVerifyLeetcode.textContent = "Verified ✓";
    btnVerifyLeetcode.disabled = true;
  } else {
    btnVerifyLeetcode.textContent = "Verify Solve on LeetCode API";
    btnVerifyLeetcode.disabled = false;
  }

  if (state.completed_quests_today.includes("agility_code")) {
    btnCompleteAgility.textContent = "Claimed ✓";
    btnCompleteAgility.disabled = true;
  } else {
    btnCompleteAgility.textContent = "Claim Quest Complete";
    btnCompleteAgility.disabled = false;
  }

  // Update Shop Item XP Badges
  const claimedRewards = state.claimed_rewards_today || [];
  document.querySelectorAll(".shop-item").forEach(item => {
    const itemId = item.getAttribute("data-id");
    const badge = item.querySelector(".shop-badge");
    
    const baseCosts = {
      "ammu_chat": 0,
      "park_walk": 0,
      "music_session": 0,
      "chess_match": 20,
      "movie_session": 60,
      "buy_dress": 100,
      "travel_trip": 250
    };
    
    let cost = baseCosts[itemId] || 0;
    const claimedCount = claimedRewards.filter(id => id === itemId).length;
    if (baseCosts[itemId] === 0 && claimedCount >= 1) {
      cost = 10;
    }
    
    badge.textContent = `${cost} XP`;
  });

  // Lockscreen activation
  if (state.lockout_active) {
    lockScreen.style.display = "flex";
  } else {
    lockScreen.style.display = "none";
  }
}

// Ingest Telemetry
document.getElementById("telemetry-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const study_hours = parseFloat(studyHoursInput.value);
  const gym_hours = parseFloat(gymHoursInput.value);
  const dopamine_rewards = parseInt(dopamineRewardsInput.value);

  try {
    const res = await fetch("/api/telemetry/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ study_hours, gym_hours, dopamine_rewards })
    });
    const result = await res.json();
    alert(result.message || "Telemetry logged successfully!");
    
    // Reset inputs
    studyHoursInput.value = 0; studyLabel.textContent = "0";
    gymHoursInput.value = 0; gymLabel.textContent = "0";
    dopamineRewardsInput.value = 0; dopamineLabel.textContent = "0";
    
    fetchStatus();
  } catch (err) {
    alert("Error submitting telemetry log.");
  }
});

// Toggle checklist items
async function toggleChecklist(item, value) {
  // Offline state prediction
  if (currentState) {
    currentState[`${item}_completed`] = value;
    if (value) {
      if (item === "gym" || item === "cooking") currentState.xp += 10;
      else if (item === "nopmo") {
        currentState.xp += 15;
        currentState.willpower = (currentState.willpower || 10) + 1;
      }
    } else {
      if (item === "gym" || item === "cooking") currentState.xp = Math.max(0, currentState.xp - 10);
      else if (item === "nopmo") {
        currentState.xp = Math.max(0, currentState.xp - 15);
        currentState.willpower = Math.max(0, (currentState.willpower || 10) - 1);
      }
    }
    
    // Level up check offline
    let reqXp = Math.floor(100 * Math.pow(currentState.level, 1.5));
    while (currentState.xp >= reqXp) {
      currentState.xp -= reqXp;
      currentState.level++;
      reqXp = Math.floor(100 * Math.pow(currentState.level, 1.5));
    }
    
    localStorage.setItem("antigravity_state", JSON.stringify(currentState));
    updateUI(currentState);
  }

  try {
    const res = await fetch("/api/checklist/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item, value })
    });
    const state = await res.json();
    currentState = state;
    localStorage.setItem("antigravity_state", JSON.stringify(state));
    updateUI(state);
  } catch (err) {
    console.warn("Offline: Checklist toggle saved locally.");
  }
}

checkGym.addEventListener("change", (e) => toggleChecklist("gym", e.target.checked));
checkCooking.addEventListener("change", (e) => toggleChecklist("cooking", e.target.checked));
checkNopmo.addEventListener("change", (e) => toggleChecklist("nopmo", e.target.checked));

// Verify LeetCode Quest
btnVerifyLeetcode.addEventListener("click", async () => {
  btnVerifyLeetcode.textContent = "Checking GraphQL...";
  btnVerifyLeetcode.disabled = true;
  try {
    const res = await fetch("/api/quest/complete?quest_type=core_skill", { method: "POST" });
    const result = await res.json();
    if (res.ok) {
      alert(result.message);
    } else {
      alert(`Verification Failed: ${result.detail}`);
    }
    fetchStatus();
  } catch (err) {
    alert("Error contacting verification endpoint.");
    btnVerifyLeetcode.disabled = false;
  }
});

// Verify Agility Quest
btnCompleteAgility.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/quest/complete?quest_type=agility_code", { method: "POST" });
    const result = await res.json();
    if (res.ok) {
      alert(result.message);
    } else {
      alert(`Verification Failed: ${result.detail}`);
    }
    fetchStatus();
  } catch (err) {
    alert("Error completing quest.");
  }
});

// Claim Dopamine reward
document.querySelectorAll(".shop-item").forEach(item => {
  const btn = item.querySelector(".btn-shop");
  const itemId = item.getAttribute("data-id");
  
  btn.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/dopamine/claim", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_id: itemId })
      });
      const result = await res.json();
      if (res.ok) {
        alert(result.message);
      } else {
        alert(`Claim Denied: ${result.detail}`);
      }
      fetchStatus();
    } catch (err) {
      alert("Error logging claim.");
    }
  });
});

// Fetch Lockscreen Mathematical Proof
async function fetchMathChallenge() {
  try {
    const res = await fetch("/api/dungeon/challenge");
    const data = await res.json();
    mathQuestion.textContent = data.question;
  } catch (err) {
    mathQuestion.textContent = "Error fetching math challenge.";
  }
}

// Cleanse Dungeon - Physical Pushups
btnSubmitPushups.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/dungeon/cleanse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload_type: "physical", solution: "100" })
    });
    const result = await res.json();
    if (res.ok) {
      alert(result.message);
      fetchStatus();
    } else {
      alert(`Cleanse Failed: ${result.detail}`);
    }
  } catch (err) {
    alert("Error submitting physical cleanse.");
  }
});

// Cleanse Dungeon - Math
btnSubmitMath.addEventListener("click", async () => {
  const solution = mathAnswer.value.trim();
  if (!solution) return alert("Please type your solution.");
  
  try {
    const res = await fetch("/api/dungeon/cleanse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload_type: "mathematical", solution })
    });
    const result = await res.json();
    if (res.ok) {
      alert(result.message);
      mathAnswer.value = "";
      fetchStatus();
    } else {
      alert(`Validation Failed: ${result.detail}`);
    }
  } catch (err) {
    alert("Error verifying proof.");
  }
});

// Toggle settings modal views
btnSettings.addEventListener("click", () => {
  settingsModal.style.display = "flex";
});

btnCloseSettings.addEventListener("click", () => {
  settingsModal.style.display = "none";
});

// Emergency Bypass Lockout
btnEmergencyBypass.addEventListener("click", async () => {
  const confirmBypass = confirm("WARNING: Are you sure you want to trigger the Emergency Bypass?\n\nThis will instantly lift the lockout, but you will be penalized:\n-5 Willpower (WIL)\n-100 XP");
  if (!confirmBypass) return;
  
  try {
    const res = await fetch("/api/dungeon/cleanse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload_type: "emergency", solution: "bypass" })
    });
    const result = await res.json();
    if (res.ok) {
      alert(result.message);
      settingsModal.style.display = "none";
      lockScreen.style.display = "none";
      fetchStatus();
    } else {
      alert(`Emergency Bypass Failed: ${result.detail}`);
    }
  } catch (err) {
    alert("Error submitting emergency bypass.");
  }
});

// Initial Setup Load
fetchStatus();
fetchSyllabus();
// Auto-sync status every 20 seconds
setInterval(fetchStatus, 20000);

// ==========================================
// VIT Syllabus Progress Tracker Logic
// ==========================================

let syllabusCatalog = null;
let expandedWeeks = {};

const courseTabs = document.getElementById("course-tabs");
const courseProgressFill = document.getElementById("course-progress-fill");
const coursePctLabel = document.getElementById("course-pct-label");
const weeksList = document.getElementById("weeks-list");

// Fetch the full coursework definitions
async function fetchSyllabus() {
  try {
    const res = await fetch("/api/syllabus");
    syllabusCatalog = await res.json();
    renderSyllabus();
  } catch (err) {
    console.error("Error loading syllabus database:", err);
  }
}

// Render course chips horizontally
function renderCourseTabs(activeSub) {
  if (!courseTabs || !syllabusCatalog) return;
  
  courseTabs.innerHTML = "";
  
  const courseOrder = [
    "Python_Data_Science",
    "Linear_Algebra",
    "Probability_Stats",
    "Statistical_Inference",
    "EDA",
    "Database_Systems",
    "Data_Mining_Forecasting",
    "Advanced_Forecasting",
    "DSA_LeetCode",
    "AI_Agents",
    "Machine_Learning"
  ];
  
  courseOrder.forEach(key => {
    const course = syllabusCatalog.courses[key];
    if (!course) return;
    
    const chip = document.createElement("div");
    chip.className = `course-chip ${key === activeSub ? 'active' : ''}`;
    
    const shortNames = {
      "Python_Data_Science": "Python",
      "Linear_Algebra": "Algebra",
      "Probability_Stats": "Probability",
      "Statistical_Inference": "Inference",
      "EDA": "EDA",
      "Database_Systems": "DBMS",
      "Data_Mining_Forecasting": "Mining",
      "Advanced_Forecasting": "Forecast",
      "DSA_LeetCode": "DSA / LeetCode",
      "AI_Agents": "AI Agents",
      "Machine_Learning": "Machine Learning"
    };
    
    chip.textContent = shortNames[key] || course.name;
    chip.addEventListener("click", () => setActiveCourse(key));
    courseTabs.appendChild(chip);
  });
  
  // Auto-scroll the active chip into view horizontally
  const activeChip = courseTabs.querySelector(".course-chip.active");
  if (activeChip) {
    activeChip.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }
}

// Trigger active course change
async function setActiveCourse(subjectId) {
  if (currentState) {
    currentState.active_subject = subjectId;
    localStorage.setItem("antigravity_state", JSON.stringify(currentState));
    expandedWeeks = {};
    updateUI(currentState);
    renderSyllabus();
  }

  try {
    const res = await fetch("/api/syllabus/active", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject_id: subjectId })
    });
    const state = await res.json();
    currentState = state;
    localStorage.setItem("antigravity_state", JSON.stringify(state));
    expandedWeeks = {};
    updateUI(state);
    renderSyllabus();
  } catch (err) {
    console.warn("Offline: Active course change registered locally.");
  }
}

// Render dynamic weekly modules
function renderSyllabus() {
  if (!syllabusCatalog || !currentState) return;
  
  const activeSub = currentState.active_subject || "Python_Data_Science";
  renderCourseTabs(activeSub);
  
  const course = syllabusCatalog.courses[activeSub];
  if (!course) return;
  
  const completedItems = currentState.completed_syllabus_items[activeSub] || [];
  
  let totalCourseItems = 0;
  let completedCourseItems = 0;
  
  weeksList.innerHTML = "";
  
  course.weeks.forEach(week => {
    const weekNum = week.week;
    const weekTitle = week.title;
    const items = week.items;
    
    totalCourseItems += items.length;
    
    let completedWeekItems = 0;
    const itemRows = items.map(item => {
      const isChecked = completedItems.includes(item.id);
      if (isChecked) {
        completedWeekItems++;
        completedCourseItems++;
      }
      
      return `
        <label class="syllabus-item">
          <input type="checkbox" class="syllabus-item-chk" data-item-id="${item.id}" ${isChecked ? 'checked' : ''}>
          <span class="syllabus-checkbox-custom"></span>
          <div class="syllabus-item-details">
            <span class="syllabus-item-name">${item.name}</span>
            <div class="syllabus-item-meta">
              <span class="syllabus-item-date" style="font-size: 0.65rem; color: var(--text-muted); margin-right: 6px;">📅 ${item.date}</span>
              <span class="syllabus-item-type ${item.type}">${item.type}</span>
              <span class="syllabus-item-xp">+${item.xp} XP</span>
            </div>
          </div>
        </label>
      `;
    }).join("");
    
    const isWeekComplete = completedWeekItems === items.length;
    const isExpanded = expandedWeeks[weekNum] || false;
    
    const weekCard = document.createElement("div");
    weekCard.className = `week-card ${isWeekComplete ? 'completed' : ''} ${isExpanded ? 'expanded' : ''}`;
    weekCard.innerHTML = `
      <div class="week-header">
        <div class="week-title-container">
          <span class="week-num">WEEK ${weekNum} (${week.start_date} to ${week.end_date})</span>
          <span class="week-title">${weekTitle}</span>
        </div>
        <span class="week-badge">${completedWeekItems}/${items.length}</span>
      </div>
      <div class="week-items" style="display: ${isExpanded ? 'flex' : 'none'};">
        ${itemRows}
      </div>
    `;
    
    // Expand/Collapse accordion trigger
    weekCard.querySelector(".week-header").addEventListener("click", () => {
      const isNowExpanded = !expandedWeeks[weekNum];
      expandedWeeks[weekNum] = isNowExpanded;
      weekCard.classList.toggle("expanded", isNowExpanded);
      weekCard.querySelector(".week-items").style.display = isNowExpanded ? "flex" : "none";
    });
    
    // Checkbox checklist toggle triggers
    weekCard.querySelectorAll(".syllabus-item-chk").forEach(chk => {
      chk.addEventListener("change", async (e) => {
        const itemId = e.target.getAttribute("data-item-id");
        const completed = e.target.checked;
        await toggleSyllabusItem(activeSub, itemId, completed);
      });
    });
    
    weeksList.appendChild(weekCard);
  });
  
  // Calculate and draw course overall progress fill
  const coursePct = totalCourseItems > 0 ? Math.round((completedCourseItems / totalCourseItems) * 100) : 0;
  courseProgressFill.style.width = `${coursePct}%`;
  coursePctLabel.textContent = `${coursePct}%`;
}

// Toggle completion checklist and save state
async function toggleSyllabusItem(subjectId, itemId, completed) {
  // Offline state prediction
  if (currentState) {
    const completedList = currentState.completed_syllabus_items[subjectId] || [];
    const targetItem = findSyllabusItem(subjectId, itemId);
    const xpVal = targetItem ? targetItem.xp : 5;

    if (completed) {
      if (!completedList.includes(itemId)) {
        completedList.push(itemId);
        currentState.xp += xpVal;
      }
    } else {
      const idx = completedList.indexOf(itemId);
      if (idx > -1) {
        completedList.splice(idx, 1);
        currentState.xp = Math.max(0, currentState.xp - xpVal);
      }
    }
    currentState.completed_syllabus_items[subjectId] = completedList;
    
    // Level up check offline
    let reqXp = Math.floor(100 * Math.pow(currentState.level, 1.5));
    while (currentState.xp >= reqXp) {
      currentState.xp -= reqXp;
      currentState.level++;
      reqXp = Math.floor(100 * Math.pow(currentState.level, 1.5));
    }

    localStorage.setItem("antigravity_state", JSON.stringify(currentState));
    updateUI(currentState);
    renderSyllabus();
  }

  try {
    const res = await fetch("/api/syllabus/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject_id: subjectId, item_id: itemId, completed })
    });
    const state = await res.json();
    currentState = state;
    localStorage.setItem("antigravity_state", JSON.stringify(state));
    updateUI(state);
    renderSyllabus();
  } catch (err) {
    console.warn("Offline: Syllabus toggle registered locally.");
  }
}

// Helper to query syllabus database item locally when offline
function findSyllabusItem(subjectId, itemId) {
  if (!syllabusCatalog) return null;
  const course = syllabusCatalog.courses[subjectId];
  if (!course) return null;
  for (const week of course.weeks) {
    for (const item of week.items) {
      if (item.id === itemId) return item;
    }
  }
  return null;
}

// Course selection events handled via dynamic event listeners inside renderCourseTabs

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
