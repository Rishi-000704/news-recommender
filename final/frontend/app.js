const api = "http://localhost:8000";

// ─── Authentication Check ──────────────────────────────────────

function initAuth() {
  const isGuest = localStorage.getItem('isGuest') === 'true';
  const userId = localStorage.getItem('userId');
  
  // Redirect to login if not authenticated and not guest
  if (!userId && !isGuest) {
    window.location.href = 'login.html';
    return false;
  }
  
  return true;
}

// Initialize auth on page load
if (!initAuth()) {
  throw new Error('Not authenticated');
}

let userId = "";

let queue = [];
let currentIndex = 0;
let startedAt = Date.now();
let attentionScore = 0.5;
let latestAttention = {
  brightness: 50, eye_openness: 70, movement: 20,
  energy_score: 63.5, gaze_score: 0.58, attention_score: 0.0,
  normalized_attention: 0.5, eye_aspect_ratio: 0.25,
  eye_movement: 0.0, face_distance: 0.5, distance_ok: true,
  head_movement: 0.0, face_detected: false, state: "no_face",
  source: "fallback", status: "idle",
};
let cameraActive = false;
let frameInterval = null;       // webcam frame polling
let attentionInterval = null;   // /attention JSON polling
let pollTimer = null;
let scrollDepth = 0;
let userMood = "";
let userLocation = "";
let currentPollVal = 0.5;         // updated when user answers poll
let currentLongTermHistory = 0.2; // updated from user profile on each load

const $ = (id) => document.getElementById(id);

// ─── Network helpers ──────────────────────────────────────────

async function post(path, body) {
  const headers = { "Content-Type": "application/json" };
  const token = localStorage.getItem('token');
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  const res = await fetch(`${api}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  
  if (!res.ok) {
    const text = await res.text();
    if (res.status === 401) {
      // Token expired, redirect to login
      localStorage.clear();
      window.location.href = 'login.html';
    }
    throw new Error(text);
  }
  
  return res.json();
}

// ─── Bar helper ───────────────────────────────────────────────
// barId  = id of the .abar container (holds --pct CSS var)
// spanId = id of the value <span>
// value  = raw numeric value
// max    = value that means 100% bar
// dec    = decimal places for display
// invert = true → bar fills MORE when value is LOW (e.g. movement)

function setBar(barId, spanId, value, max = 100, dec = 0, invert = false) {
  const num = Number(value) || 0;
  const el = $(spanId);
  if (el) el.textContent = num.toFixed(dec);
  let pct = Math.min(100, (num / max) * 100);
  if (invert) pct = Math.max(0, 100 - pct);
  const bar = $(barId);
  if (bar) bar.style.setProperty("--pct", `${pct.toFixed(1)}%`);
}

// ─── Data loading ─────────────────────────────────────────────

async function loadCategories() {
  try {
    const res = await fetch(`${api}/categories`);
    const data = await res.json();
    const container = $("interestOptions");
    container.innerHTML = "";
    (data.categories || []).forEach((cat) => {
      const label = document.createElement("label");
      label.className = "checkbox-item";
      const cb = document.createElement("input");
      cb.type = "checkbox"; cb.name = "interest"; cb.value = cat;
      if (["technology", "health", "sports"].includes(cat)) cb.checked = true;
      label.append(cb, document.createTextNode(cat));
      container.appendChild(label);
    });
  } catch (e) { console.warn("loadCategories:", e); }
}

async function loadUserIds() {
  try {
    const res = await fetch(`${api}/users`);
    const data = await res.json();
    const dl = $("userOptions");
    if (dl) {
      dl.innerHTML = "";
      (data.users || []).forEach((id) => {
        const opt = document.createElement("option"); opt.value = id;
        dl.appendChild(opt);
      });
    }
    const known = $("knownUsers");
    if (known) {
      const list = data.users || [];
      known.textContent = list.length
        ? `${list.length} users: ${list.slice(0, 12).join(", ")}${list.length > 12 ? " …" : ""}`
        : "none yet";
    }
  } catch (e) { console.warn("loadUserIds:", e); }
}

async function loadUserInfo(uid) {
  if (!uid) return;
  try {
    const res = await fetch(`${api}/user/${encodeURIComponent(uid)}`);
    if (!res.ok) return;
    const u = await res.json();
    $("userIdDisplay").textContent       = u.user_id || "—";
    $("userInterestsDisplay").textContent = u.user_interest_text || "—";
    $("userMoodDisplay").textContent      = u.mood || "—";
    $("userAttentionDisplay").textContent    = Number(u.attention_score    || 0).toFixed(2);
    $("userInteractionDisplay").textContent  = Number(u.interaction_score  || 0).toFixed(2);
    $("userExplorationDisplay").textContent  = Number(u.exploration_signal || 0).toFixed(2);
    userMood = u.mood || userMood;
    userLocation = u.current_location || u.location || userLocation;
    currentLongTermHistory = Number(u.interaction_score || 0.2);
  } catch (e) { console.warn("loadUserInfo:", e); }
}

function selectedInterests() {
  return Array.from(document.querySelectorAll("#interestOptions input:checked")).map(i => i.value);
}

// ─── Attention polling ────────────────────────────────────────

async function fetchAttention() {
  try {
    const res = await fetch(`${api}/attention`);
    if (!res.ok) return;

    const data = await res.json();
    latestAttention = { ...latestAttention, ...data };

    // 🔥 FIX: ALWAYS USE NORMALIZED FIRST
    let norm = Number(data.normalized_attention);

    if (!Number.isFinite(norm)) {
      const raw = Number(data.attention_score || 0);
      norm = raw > 1 ? raw / 100 : raw;
    }

    // 🔥 FINAL SAFETY CLAMP
    attentionScore = Math.max(0, Math.min(1, norm));

    updateAttentionDisplay();
  } catch (e) {
    console.warn("Attention fetch failed", e);
  }
}

function startAttentionPolling(fast = false) {
  stopAttentionPolling();
  attentionInterval = setInterval(fetchAttention, fast ? 500 : 1200);
}

function stopAttentionPolling() {
  clearInterval(attentionInterval);
  attentionInterval = null;
}

function updateAttentionDisplay() {
  const a = latestAttention;
  const state = (a.state || "no_face").toLowerCase();

  $("attention").textContent = attentionScore.toFixed(2);

  const badge = $("attentionStatus");
  badge.textContent = a.face_detected ? state.toUpperCase() : "NO FACE";
  badge.className = "state-badge" + (a.face_detected ? " " + state : "");

  setBar("bar-brightness", "brightness",  a.brightness, 100, 0);
  setBar("bar-eye",        "eyeOpen",     a.eye_openness, 100, 0);
  setBar("bar-ear",        "eyeEar",      a.eye_aspect_ratio, 0.5, 2);
  setBar("bar-eyemove",    "eyeMove",     a.eye_movement, 20, 1);
  setBar("bar-movement",   "movement",    a.movement, 100, 0, true);
  setBar("bar-energy",     "energy",      a.energy_score, 100, 0);
  setBar("bar-gaze",       "gaze",        a.gaze_score, 1, 2);
  setBar("bar-distance",   "distance",    a.face_distance, 1, 2);

  $("headMovement").textContent = Number(a.head_movement || 0).toFixed(1);
  $("distanceOk").textContent = a.distance_ok ? "✓" : "✗";
}


// ─── Camera (frame polling — works in all browsers) ───────────

async function pollFrame() {
  if (!cameraActive) return;
  try {
    // Bypass any cache with timestamp param
    const res = await fetch(`${api}/attention/frame?t=${Date.now()}`);
    if (!res.ok) return;
    const blob = await res.blob();
    const img = $("cameraFeed");
    const prev = img.dataset.blobUrl;
    const url = URL.createObjectURL(blob);
    img.src = url;
    img.style.display = "block";
    if (prev) URL.revokeObjectURL(prev);
    img.dataset.blobUrl = url;

    const ph = $("cameraPlaceholder");
    if (ph) ph.style.display = "none";

    // Update status text on first successful frame
    const msg = $("cameraMessage");
    if (msg && msg.textContent !== "Live") msg.textContent = "Live";
  } catch {
    // frame not ready yet
  }
}

function startFramePolling() {
  if (frameInterval) return;
  frameInterval = setInterval(pollFrame, 80); // ~12 fps
}

function stopFramePolling() {
  clearInterval(frameInterval);
  frameInterval = null;
  // Clean up last blob URL
  const img = $("cameraFeed");
  if (img?.dataset?.blobUrl) {
    URL.revokeObjectURL(img.dataset.blobUrl);
    delete img.dataset.blobUrl;
  }
}

function startMjpegStream() {
  const panel = $("cameraPanel");
  const btn   = $("webcamBtn");
  panel?.classList.add("cam-active");
  btn?.classList.add("cam-active");
  cameraActive = true;
  $("cameraMessage").textContent = "Connecting to camera…";
  btn.innerHTML = '<span class="cam-dot"></span> Stop webcam';
  startFramePolling();
  startAttentionPolling(true); // fast polling while webcam active
}

function stopMjpegStream() {
  const img   = $("cameraFeed");
  const ph    = $("cameraPlaceholder");
  const panel = $("cameraPanel");
  const btn   = $("webcamBtn");

  stopFramePolling();
  img.src = "";
  img.style.display = "none";
  if (ph) ph.style.display = "flex";
  panel?.classList.remove("cam-active");
  btn?.classList.remove("cam-active");
  cameraActive = false;
  $("cameraMessage").textContent = "Not started";
  btn.innerHTML = '<span class="cam-dot"></span> Start webcam';
  startAttentionPolling(false); // back to slow polling
}

// ─── Article rendering ────────────────────────────────────────

function currentItem() { return queue[currentIndex]; }

function resetTimer() {
  startedAt = Date.now();
  currentPollVal = 0.5;
  const t = $("timer"); if (t) t.textContent = "0.0s";
  const m = $("manualTime"); if (m) m.value = "";
}

function paintCard() {
  const item = currentItem();
  if (!item) return;
  hidePoll();
  resetScrollTracking();
  scheduleInterestPoll();

  // Re-trigger slide-in animation
  const card = $("card");
  if (card) { card.style.animation = "none"; void card.offsetWidth; card.style.animation = ""; }

  $("category").textContent = `${item.category}${item.source_mix ? " · " + item.source_mix : ""}`;

  const dec = $("decision");
  dec.textContent = (item.hitl_decision || "keep").replace(/_/g, " ");
  dec.className   = "chip chip-decision"
    + (item.hitl_decision === "auto_skip"   ? " skip" : "")
    + (item.hitl_decision === "ask_continue"? " ask"  : "");

  $("headline").textContent = item.full_article
    ? item.full_article.split(".")[0]
    : item.abstract || item.news_id;
  $("abstract").textContent = item.abstract || item.full_article || "No summary available.";

  const urlEl = $("url");
  if (item.url) { urlEl.classList.remove("hidden"); urlEl.href = item.url; }
  else          { urlEl.classList.add("hidden"); }

  // Score tiles
  const score = Number(item.score    || 0);
  const qv    = Number(item.q_value  || 0);
  const sim   = Number(item.similarity || 0);
  const trend = Number(item.trending || 0);

  $("score").textContent = score.toFixed(2);
  const qEl = $("q-val");   if (qEl) qEl.textContent = qv.toFixed(2);
  const sEl = $("sim-val"); if (sEl) sEl.textContent = sim.toFixed(2);
  const tEl = $("trend-val"); if (tEl) tEl.textContent = trend.toFixed(2);
  const why = $("why"); if (why) why.textContent = `q ${qv.toFixed(2)} - sim ${sim.toFixed(2)} - trend ${trend.toFixed(2)}`;

  renderQueue();
  resetTimer();

  // Immediately refresh live attention values for this new card
  fetchAttention();

  if (item.hitl_decision === "auto_skip") {
    const nid = item.news_id;
    const delay = attentionScore < 0.35 || score < 0.1 ? 9000 : 20000;
    setTimeout(() => { if (currentItem()?.news_id === nid) sendFeedback(0, 1, true); }, delay);
  }
}

function renderQueue() {
  const list = $("queueList");
  list.innerHTML = "";
  queue.forEach((item, i) => {
    const li = document.createElement("li");
    li.className = i === currentIndex ? "active" : "";
    li.textContent = `${item.category}: ${(item.abstract || item.news_id || "").slice(0, 90)}`;
    li.addEventListener("click", () => { currentIndex = i; paintCard(); });
    list.appendChild(li);
  });
}

// ─── Queue manipulation helpers ───────────────────────────────

function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

function reorderQueueAfterLike(likedCategory) {
  const before    = queue.slice(0, currentIndex);
  const remaining = queue.slice(currentIndex);

  const samecat = remaining.filter(item => item.category === likedCategory);
  const others  = remaining.filter(item => item.category !== likedCategory);

  // Place 2–3 same-category articles spread across the next 6 slots
  const targetCount = Math.min(samecat.length, Math.floor(Math.random() * 2) + 2); // 2 or 3
  const promoted    = samecat.slice(0, targetCount);
  const restSamecat = samecat.slice(targetCount);

  const fillCount    = Math.max(0, 6 - promoted.length);
  const windowOthers = others.slice(0, fillCount);
  const afterWindow  = [...restSamecat, ...others.slice(fillCount)];

  // Shuffle the 6-slot window so promoted items aren't all at the very front
  const window6 = shuffle([...promoted, ...windowOthers]);

  queue = [...before, ...window6, ...shuffle(afterWindow)];
}

function suppressCategory(category) {
  const before    = queue.slice(0, currentIndex);
  const remaining = queue.slice(currentIndex);

  // Within the next 5 slots allow at most 1 of the disliked category
  const window5   = remaining.slice(0, 5);
  const afterWindow = remaining.slice(5);

  const samecatInWindow = window5.filter(item => item.category === category);
  const othersInWindow  = window5.filter(item => item.category !== category);

  const keepOne = samecatInWindow.slice(0, 1);   // keep 1
  const extras  = samecatInWindow.slice(1);       // push the rest past the window

  const newWindow5 = shuffle([...othersInWindow, ...keepOne]);

  queue = [...before, ...newWindow5, ...afterWindow, ...extras];
}

async function refreshRecommendations(mode = null) {
  const data = await post("/recommend", {
    user_id: userId,
    k: 8,
    mode,
    location: userLocation,
    mood: userMood,
  });
  queue = data.recommendations || [];
  currentIndex = 0;
  paintCard();
  await Promise.all([loadUserInfo(userId), loadUserIds()]);
}

// ─── Feedback ─────────────────────────────────────────────────

async function sendFeedback(liked, skipped = 0, automatic = false, forceTrending = false) {
  const item = currentItem();
  if (!item) return;

  const elapsed = (Date.now() - startedAt) / 1000;
  const manual  = Number($("manualTime")?.value);
  const timeSpent = Number.isFinite(manual) && manual > 0 ? manual : elapsed;

  // Snapshot current attention for this interaction
  await post("/feedback", {
    user_id:          userId,
    news_id:          item.news_id,
    time_spent:       timeSpent,
    liked,
    skipped,
    scroll_depth:     scrollDepth || (liked ? 0.9 : 0.15),
    click_val:        liked ? 1 : 0,
    attention_score:  attentionScore,
    normalized_attention: attentionScore,
    brightness:       latestAttention.brightness,
    eye_openness:     latestAttention.eye_openness,
    movement:         latestAttention.movement,
    energy_score:     latestAttention.energy_score,
    gaze_score:       latestAttention.gaze_score,
    face_detected:    latestAttention.face_detected ? 1 : 0,
    attention_source: latestAttention.source || "frontend",
    final_score:      item.score,
    similarity:       item.similarity,
    trending:         item.trending,
    poll_val:         currentPollVal,
  });

  currentIndex += 1;
  hidePoll();

  // Apply like/dislike queue reshaping
  if (liked === 1) {
    reorderQueueAfterLike(item.category);
  } else if (!automatic) {
    suppressCategory(item.category);
  }

  // Refresh attention + user profile after every single article
  await Promise.all([fetchAttention(), loadUserInfo(userId)]);

  if (currentIndex >= queue.length || forceTrending || currentIndex % 3 === 0) {
    console.log("🔄 Refreshing recommendations dynamically");
    await refreshRecommendations(forceTrending ? "trending" : null);
  } else {
    paintCard();
  }
}

// ─── Poll ─────────────────────────────────────────────────────

function resetScrollTracking() {
  scrollDepth = 0;
  window.scrollTo({ top: 0, behavior: 'instant' });
}

function scheduleInterestPoll() {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(() => {
    if ($("pollPrompt")?.classList.contains("hidden") && (attentionScore < 0.55 || scrollDepth < 0.25)) {
      showPoll();
    }
  }, 20000);
}

function showPoll() {
  const item = currentItem();
  const nameEl = $("pollArticleName");
  if (nameEl && item) {
    const raw = item.full_article
      ? item.full_article.split(".")[0]
      : (item.abstract || item.news_id || "this article");
    const title = raw.slice(0, 65);
    nameEl.textContent = title + (raw.length > 65 ? "…" : "");
  }
  $("pollPrompt")?.classList.remove("hidden");
}
function hidePoll() { $("pollPrompt")?.classList.add("hidden"); clearTimeout(pollTimer); }

window.addEventListener("scroll", () => {
  const maxScroll = document.body.scrollHeight - window.innerHeight;
  if (maxScroll <= 0) return;
  scrollDepth = Math.max(scrollDepth, Math.min(1, window.scrollY / maxScroll));
});

async function sendPollFeedback(liked) {
  const item = currentItem();
  if (!item) return;
  currentPollVal = liked ? 1.0 : 0.0;  // record poll answer for interaction score
  hidePoll();
  try {
    await post("/poll_feedback", {
      user_id: userId,
      news_id: item.news_id,
      liked,
    });
  } catch (e) {
    console.warn("Poll feedback failed:", e);
  }
  if (!liked) {
    await sendFeedback(0, 1, true);
  }
}

$("pollYes").addEventListener("click", () => sendPollFeedback(1));
$("pollNo").addEventListener("click",  () => sendPollFeedback(0));

// ─── Onboard ──────────────────────────────────────────────────

$("onboardForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = new FormData(e.currentTarget);
  const btn  = e.currentTarget.querySelector('button[type="submit"]');
  const orig = btn?.textContent;
  if (btn) { btn.disabled = true; btn.textContent = "Launching…"; }

  const interests = selectedInterests();
  const entered = String(form.get("user_id") || "").trim();
  userId = entered || `user_${Math.floor(Math.random() * 90000 + 10000)}`;

  try {
    await post("/onboard", {
      user_id:               userId,
      interests:             interests.length ? interests : [String(form.get("sample_click") || "general")],
      mood:                  form.get("mood"),
      time_available:        Number(form.get("time_available")),
      time_of_day:           form.get("time_of_day"),
      location:              form.get("location"),
      exploration_preference: Number(form.get("exploration_preference")),
      sample_click:          form.get("sample_click"),
    });
    if (!entered) {
      const inp = document.querySelector("input[name='user_id']");
      if (inp) inp.value = userId;
    }
    $("userLabel").textContent = userId;
    $("onboarding").classList.add("hidden");
    $("feed").classList.remove("hidden");
    await loadUserInfo(userId);
    await refreshRecommendations();
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = orig; }
  }
});

// ─── Button handlers ──────────────────────────────────────────

$("likeBtn").addEventListener("click",    () => sendFeedback(1, 0));
$("skipBtn").addEventListener("click",    () => sendFeedback(0, 1));
$("nextBtn").addEventListener("click",    () => sendFeedback(0, 1, true));
$("refreshBtn").addEventListener("click", refreshRecommendations);

$("webcamBtn").addEventListener("click", async () => {
  if (cameraActive) {
    stopMjpegStream();
    await post("/attention/stop", {}).catch(() => {});
    return;
  }

  $("attentionStatus").textContent = "STARTING";

  try {
    const res = await post("/attention/start", {});

    if (res.status === "started" || res.status === "already_running") {
      cameraActive = true;

      startFramePolling();
      startAttentionPolling(true);

      $("cameraMessage").textContent = "Live";
      $("webcamBtn").classList.add("cam-active");

      // 🔥 FORCE FIRST UPDATE
      setTimeout(fetchAttention, 300);
    } else {
      $("cameraMessage").textContent = res.message;
    }
  } catch (err) {
    $("cameraMessage").textContent = err.message;
  }
});

// ─── Timer display (250 ms) ───────────────────────────────────

setInterval(() => {
  const elapsed = (Date.now() - startedAt) / 1000;

  const t = $("timer");
  if (t) t.textContent = `${elapsed.toFixed(1)}s`;

  if (elapsed > 20 && currentItem()) showPoll();

  // Live interaction score: 0.55·click(0.5) + 0.10·poll + 0.20·log_dwell + 0.15·history
  const logDwell  = Math.min(1.0, Math.log(elapsed + 1.0) / Math.log(61.0));
  const liveIS    = (0.55 * 0.5) + (0.10 * currentPollVal) + (0.20 * logDwell) + (0.15 * currentLongTermHistory);
  const isEl = $("interactionLive");
  if (isEl) isEl.textContent = Math.min(1, liveIS).toFixed(2);
}, 250);

// ─── Always-on attention polling (even without webcam) ────────
// Runs at 1.2 s when webcam is off; upgraded to 500 ms when webcam active

startAttentionPolling(false);

// ─── User Menu Handler ────────────────────────────────────────

const userMenuBtn = $("userMenuBtn");
const menuDropdown = $("menuDropdown");
const userEmail = $("userEmail");
const logoutLink = $("logoutLink");

// Display user username if logged in
const username = localStorage.getItem('username');
if (username && userEmail) {
  userEmail.textContent = username;
}

// Toggle menu
if (userMenuBtn) {
  userMenuBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    if (menuDropdown.style.display === "none") {
      menuDropdown.style.display = "block";
    } else {
      menuDropdown.style.display = "none";
    }
  });
}

// Close menu on outside click
document.addEventListener("click", () => {
  if (menuDropdown && menuDropdown.style.display !== "none") {
    menuDropdown.style.display = "none";
  }
});

// Logout handler
if (logoutLink) {
  logoutLink.addEventListener("click", (e) => {
    e.preventDefault();
    localStorage.clear();
    window.location.href = "login.html";
  });
}

// ─── Init ─────────────────────────────────────────────────────

Promise.all([loadCategories(), loadUserIds()]).catch(console.error);
