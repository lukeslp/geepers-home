# Geepers Kiosk Multi-View + Immersive Chat Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the Geepers sensor dashboard into a multi-view kiosk platform with full-width/split-panel modes and an immersive conversational chat experience.

**Architecture:** Config-driven view registry loaded from `dashboard.yaml`. Views are either native (sensor grid, camera, news) or iframe-embedded external web apps. A state machine manages three modes: full-width (default), split-panel (optional), and immersive chat. All transitions use 400ms CSS morphs.

**Tech Stack:** Vanilla JS (no framework), CSS Grid/Flexbox, Flask (Python), YAML config, SSE for live data.

**Design Doc:** `docs/plans/2026-02-12-kiosk-views-chat-design.md`

---

## Task 1: Add Views Config to dashboard.yaml

**Files:**
- Modify: `dashboard.yaml` (append views section at bottom)

**Step 1: Add the views section**

Append to the end of `dashboard.yaml`:

```yaml
# View registry — defines switchable kiosk views
# type: "native" (rendered in DOM) or "iframe" (embedded web app)
# split_ok: true/false/partial — whether view works at 388px wide
views:
  - id: sensors
    label: Sensors
    type: native
    default: true
    split_ok: true

  - id: camera
    label: Camera
    type: native
    split_ok: true

  - id: news
    label: News
    type: native
    split_ok: true

  - id: earth
    label: Earth
    type: iframe
    src: https://dr.eamer.dev/datavis/dashboards/live-earth/
    split_ok: true

  - id: earthquakes
    label: Quakes
    type: iframe
    src: https://dr.eamer.dev/datavis/dashboards/earthquakes/
    split_ok: true

  - id: keep-looking
    label: UFOs
    type: iframe
    src: https://dr.eamer.dev/datavis/poems/keep-looking/
    split_ok: true

  - id: whispers
    label: Haunted
    type: iframe
    src: https://dr.eamer.dev/datavis/poems/whispers/
    split_ok: true

  - id: keep-up
    label: Rent
    type: iframe
    src: https://dr.eamer.dev/datavis/poems/keep-up/
    split_ok: true

  - id: symphony
    label: Ambient
    type: iframe
    src: https://dr.eamer.dev/datavis/dashboards/symphony/
    split_ok: partial

  - id: coinfall
    label: Crypto
    type: iframe
    src: https://dr.eamer.dev/datavis/dashboards/coinfall/
    split_ok: partial

  - id: attractive
    label: Attractors
    type: iframe
    src: https://dr.eamer.dev/datavis/attractive/
    split_ok: false

  - id: admin
    label: Admin
    type: iframe
    src: https://dr.eamer.dev/admin/
    split_ok: false
```

**Step 2: Add /api/views endpoint to web_app.py**

In `web_app.py`, inside `create_app()`, after the `/api/config` route (around line 272), add:

```python
@app.route("/api/views")
def views_config():
    """Return view registry from dashboard.yaml."""
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception:
        return jsonify({"views": []})

    views = config.get("views", [])
    return jsonify({"views": views})
```

**Step 3: Commit**

```bash
git add dashboard.yaml web_app.py
git commit -m "feat: add view registry config and /api/views endpoint"
```

---

## Task 2: Restructure HTML for Multi-View Layout

**Files:**
- Modify: `web/templates/index.html`

The key structural change: wrap the sensor grid + camera + weather cards inside a `<div class="view-content" id="view-sensors">`, and add a `<div class="views-container">` that holds all view panels. The news ticker becomes a native view. Add view tab buttons to the header.

**Step 1: Restructure the header**

Replace the current header section (lines 13-22) with:

```html
<header class="header">
  <span class="header-title">Geepers</span>
  <div class="view-tabs" id="view-tabs">
    <!-- Populated by JS from /api/views -->
  </div>
  <div class="header-status">
    <span class="dot" id="status-dot"></span>
    <button class="sensor-count-btn" id="sensor-count">0 sensors</button>
    <span id="wifi-count" class="radio-badge" title="WiFi networks nearby">-- WiFi</span>
    <span id="ble-count" class="radio-badge" title="Bluetooth devices nearby">-- BLE</span>
    <button class="split-toggle-btn" id="split-toggle" aria-label="Toggle split view" title="Split view">&#9638;</button>
    <span class="clock" id="clock">--:--</span>
  </div>
</header>
```

**Step 2: Wrap content in views container**

Replace the news ticker + sensor area sections (lines 24-108) with:

```html
<!-- ─── VIEWS CONTAINER ─── -->
<div class="views-container" id="views-container">
  <!-- Native: Sensors view -->
  <div class="view-panel active" id="view-sensors" data-view-id="sensors">
    <!-- News ticker stays at top of sensors view -->
    <div class="news-ticker" id="news-ticker">
      <span class="ticker-section" id="ticker-section"></span>
      <span class="ticker-headline" id="ticker-headline">Loading headlines...</span>
    </div>
    <section class="sensor-area">
      <div class="sensor-grid" id="sensor-grid">
        <!-- All existing sensor cards remain exactly as-is -->
        <!-- (comfort, temp, humidity, voc, uv, camera, weather) -->
      </div>
    </section>
  </div>

  <!-- Native: Camera view (full-screen camera) -->
  <div class="view-panel" id="view-camera" data-view-id="camera" style="display:none">
    <div class="camera-view-full">
      <img class="camera-feed-full" id="camera-feed-full" src="/api/camera/frame" alt="Live camera feed">
      <button class="camera-describe-btn-full" id="camera-describe-btn-full">Describe Scene</button>
      <div class="camera-description-full" id="camera-description-full">Tap "Describe Scene" to analyze.</div>
    </div>
  </div>

  <!-- Native: News view (full-screen headlines) -->
  <div class="view-panel" id="view-news" data-view-id="news" style="display:none">
    <div class="news-view-full" id="news-view-full">
      <!-- Populated by JS -->
    </div>
  </div>

  <!-- Iframe views created dynamically by JS -->
</div>
```

Note: keep all the existing sensor card HTML inside `#sensor-grid` exactly as it is (lines 33-106 of current file). Only the wrapping structure changes.

**Step 3: Verify the input bar and overlays remain unchanged**

The input bar (lines 110-119), chat panel (122-131), camera overlay (133-148), radio overlay (150-159), sensor overlay (161-170), and OSK (172-213) all stay exactly where they are. No changes needed.

**Step 4: Commit**

```bash
git add web/templates/index.html
git commit -m "feat: restructure HTML for multi-view container with header tabs"
```

---

## Task 3: Add View Switcher CSS

**Files:**
- Modify: `web/static/style.css`

**Step 1: Update the dashboard grid**

Change the `.dashboard` grid (around line 89-94) from:
```css
grid-template-rows: 42px 28px 1fr 56px;
```
to:
```css
grid-template-rows: 36px 1fr 44px;
```

This removes the dedicated ticker row (ticker now lives inside sensors view) and shrinks header + input bar for maximum content space.

**Step 2: Add view tabs CSS**

After the `.clock` styles (around line 194), add:

```css
/* ═══════════════════════════════════════
   VIEW TABS — header tab switcher
   ═══════════════════════════════════════ */

.view-tabs {
  display: flex;
  gap: var(--sp-1);
  overflow-x: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
  flex: 1;
  margin: 0 var(--sp-3);
  align-items: center;
}

.view-tabs::-webkit-scrollbar {
  display: none;
}

.view-tab {
  border: none;
  background: var(--bg-base);
  box-shadow: var(--neo-out-sm);
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-dim);
  cursor: pointer;
  white-space: nowrap;
  transition: box-shadow 0.2s var(--ease), color 0.2s var(--ease);
  touch-action: manipulation;
}

.view-tab:active {
  box-shadow: var(--neo-in-sm);
}

.view-tab.active {
  box-shadow: var(--neo-in-sm);
  color: var(--accent-warm);
  font-weight: 600;
}

.split-toggle-btn {
  border: none;
  background: var(--bg-base);
  box-shadow: var(--neo-out-sm);
  width: 28px;
  height: 24px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--text-dim);
  cursor: pointer;
  touch-action: manipulation;
  transition: box-shadow 0.2s var(--ease), color 0.2s var(--ease);
}

.split-toggle-btn:active,
.split-toggle-btn.active {
  box-shadow: var(--neo-in-sm);
  color: var(--accent-warm);
}
```

**Step 3: Add views container CSS**

After the view tabs CSS, add:

```css
/* ═══════════════════════════════════════
   VIEWS CONTAINER — holds all view panels
   ═══════════════════════════════════════ */

.views-container {
  position: relative;
  overflow: hidden;
  background: var(--bg-base);
}

.view-panel {
  position: absolute;
  inset: 0;
  display: none;
  overflow: hidden;
}

.view-panel.active {
  display: flex;
  flex-direction: column;
}

/* Iframe views fill the panel */
.view-iframe {
  width: 100%;
  height: 100%;
  border: none;
  border-radius: var(--radius-sm);
}

/* ─── Split mode ─── */

.views-container.split-mode {
  display: grid;
  grid-template-columns: 1fr 24px 1fr;
}

.views-container.split-mode .view-panel {
  position: relative;
  inset: auto;
}

.views-container.split-mode .view-panel.split-left {
  display: flex;
  flex-direction: column;
  grid-column: 1;
}

.views-container.split-mode .view-panel.split-right {
  display: flex;
  flex-direction: column;
  grid-column: 3;
}

.views-container.split-mode .view-panel:not(.split-left):not(.split-right) {
  display: none;
}

/* Panel divider */
.panel-divider {
  grid-column: 2;
  display: none;
  width: 24px;
  background: var(--bg-base);
  box-shadow: var(--neo-out-sm);
  border-radius: var(--radius-sm);
  align-items: center;
  justify-content: center;
  cursor: pointer;
  touch-action: manipulation;
  transition: box-shadow 0.15s var(--ease);
}

.views-container.split-mode .panel-divider {
  display: flex;
}

.panel-divider::before {
  content: '\u22EE\u22EE';
  font-size: 16px;
  color: var(--text-dim);
  letter-spacing: 2px;
}

.panel-divider:active {
  box-shadow: var(--neo-in-sm);
}

/* Split panel mini-headers */
.panel-mini-header {
  display: none;
  height: 24px;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--sp-2);
  flex-shrink: 0;
}

.views-container.split-mode .panel-mini-header {
  display: flex;
}

.panel-mode-select {
  background: var(--bg-base);
  box-shadow: var(--neo-in-sm);
  border: none;
  border-radius: var(--radius-pill);
  padding: 2px 8px;
  font-family: inherit;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
}

.panel-expand-btn {
  border: none;
  background: var(--bg-base);
  box-shadow: var(--neo-out-sm);
  width: 22px;
  height: 22px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-dim);
  cursor: pointer;
  touch-action: manipulation;
}

.panel-expand-btn:active {
  box-shadow: var(--neo-in-sm);
}
```

**Step 4: Update the input bar CSS**

Change `.input-bar` height and styling. Find the existing input-bar CSS and update to:

```css
.input-bar {
  display: flex;
  align-items: center;
  padding: 0 var(--sp-3);
  gap: var(--sp-2);
  background: var(--bg-base);
  z-index: 10;
  height: 44px;
}
```

**Step 5: Move the news ticker CSS into the sensors view context**

The `.news-ticker` styles stay as-is but add:

```css
/* News ticker now lives inside sensors view */
.view-panel .news-ticker {
  height: 24px;
  flex-shrink: 0;
}
```

**Step 6: Commit**

```bash
git add web/static/style.css
git commit -m "feat: add CSS for view tabs, views container, split mode, and panel dividers"
```

---

## Task 4: Implement View Manager in JavaScript

**Files:**
- Modify: `web/static/app.js`

This is the core logic. The ViewManager loads views from `/api/views`, creates DOM elements, handles tab switching, and manages iframe lazy loading.

**Step 1: Add ViewManager object**

At the top of the IIFE (after `state` declaration, around line 19), add:

```javascript
// ─── View state ───
const viewState = {
  views: [],            // view configs from /api/views
  activeViewId: null,   // currently visible view id
  splitMode: false,     // split panel active
  splitLeft: null,      // left panel view id (split mode)
  splitRight: null,     // right panel view id (split mode)
  loadedIframes: [],    // ids of iframes whose src is set (LRU order, newest last)
  MAX_IFRAMES: 3,       // max simultaneous loaded iframes (Pi memory)
};
```

**Step 2: Add loadViews function**

After the existing `loadConfig()` function (find it by searching for `async function loadConfig`), add:

```javascript
// ─── View Manager ───

async function loadViews() {
  try {
    const resp = await fetch('/api/views');
    const data = await resp.json();
    viewState.views = data.views || [];
    buildViewTabs();
    buildIframePanels();

    // Activate default view
    const defaultView = viewState.views.find(v => v.default) || viewState.views[0];
    if (defaultView) {
      activateView(defaultView.id);
    }
  } catch (err) {
    console.warn('Failed to load views:', err);
  }
}

function buildViewTabs() {
  const tabsEl = document.getElementById('view-tabs');
  if (!tabsEl) return;
  tabsEl.innerHTML = '';

  viewState.views.forEach(view => {
    const btn = document.createElement('button');
    btn.className = 'view-tab';
    btn.dataset.view = view.id;
    btn.textContent = view.label;
    btn.addEventListener('click', () => activateView(view.id));
    tabsEl.appendChild(btn);
  });
}

function buildIframePanels() {
  const container = document.getElementById('views-container');
  if (!container) return;

  viewState.views.forEach(view => {
    if (view.type !== 'iframe') return;

    // Don't create if panel already exists
    if (document.getElementById('view-' + view.id)) return;

    const panel = document.createElement('div');
    panel.className = 'view-panel';
    panel.id = 'view-' + view.id;
    panel.dataset.viewId = view.id;
    panel.style.display = 'none';

    const iframe = document.createElement('iframe');
    iframe.className = 'view-iframe';
    iframe.id = 'iframe-' + view.id;
    iframe.setAttribute('loading', 'lazy');
    iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin');
    iframe.setAttribute('title', view.label);
    // Don't set src yet — lazy load on first activation

    panel.appendChild(iframe);
    container.appendChild(panel);
  });
}

function activateView(viewId) {
  if (viewState.splitMode) {
    // In split mode, activate in focused panel
    return;
  }

  const container = document.getElementById('views-container');
  if (!container) return;

  // Deactivate all panels
  container.querySelectorAll('.view-panel').forEach(p => {
    p.classList.remove('active');
    p.style.display = 'none';
  });

  // Activate target panel
  const panel = document.getElementById('view-' + viewId);
  if (panel) {
    panel.style.display = '';
    panel.classList.add('active');
  }

  // Lazy-load iframe if needed
  const view = viewState.views.find(v => v.id === viewId);
  if (view && view.type === 'iframe') {
    lazyLoadIframe(viewId, view.src);
  }

  // Update tab active state
  document.querySelectorAll('.view-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.view === viewId);
  });

  viewState.activeViewId = viewId;
}

function lazyLoadIframe(viewId, src) {
  const iframe = document.getElementById('iframe-' + viewId);
  if (!iframe || iframe.src === src) return;

  // LRU eviction: if at max, unload oldest
  if (viewState.loadedIframes.length >= viewState.MAX_IFRAMES) {
    const evictId = viewState.loadedIframes.shift();
    const evictFrame = document.getElementById('iframe-' + evictId);
    if (evictFrame) {
      evictFrame.src = 'about:blank';
    }
  }

  // Remove if already in list (will re-add at end)
  viewState.loadedIframes = viewState.loadedIframes.filter(id => id !== viewId);

  iframe.src = src;
  viewState.loadedIframes.push(viewId);
}
```

**Step 3: Call loadViews on startup**

Find the `DOMContentLoaded` or startup section (it's an IIFE so look for `connectSSE()` call and `loadConfig()` call). After `loadConfig()`, add:

```javascript
loadViews();
```

**Step 4: Commit**

```bash
git add web/static/app.js
git commit -m "feat: add ViewManager with tab switching and iframe lazy loading"
```

---

## Task 5: Implement Split Mode

**Files:**
- Modify: `web/static/app.js` (add split mode logic)
- Modify: `web/templates/index.html` (add panel divider element)

**Step 1: Add panel divider to HTML**

In `index.html`, inside `.views-container`, after the native view panels and before `</div>`, add:

```html
<!-- Panel divider (only visible in split mode) -->
<div class="panel-divider" id="panel-divider"></div>
```

**Step 2: Add split mode functions to app.js**

After the `lazyLoadIframe` function, add:

```javascript
// ─── Split Mode ───

function toggleSplitMode() {
  const container = document.getElementById('views-container');
  const toggle = document.getElementById('split-toggle');
  if (!container) return;

  viewState.splitMode = !viewState.splitMode;

  if (viewState.splitMode) {
    enterSplitMode();
  } else {
    exitSplitMode();
  }

  if (toggle) toggle.classList.toggle('active', viewState.splitMode);
}

function enterSplitMode() {
  const container = document.getElementById('views-container');
  container.classList.add('split-mode');

  // Current view goes left, next split-compatible view goes right
  const current = viewState.activeViewId || 'sensors';
  const splitViews = viewState.views.filter(v => v.split_ok === true);
  const currentIdx = splitViews.findIndex(v => v.id === current);
  const nextIdx = (currentIdx + 1) % splitViews.length;
  const rightView = splitViews[nextIdx] || splitViews[0];

  setSplitPanels(current, rightView.id);
}

function exitSplitMode() {
  const container = document.getElementById('views-container');
  container.classList.remove('split-mode');

  // Clean up split classes
  container.querySelectorAll('.view-panel').forEach(p => {
    p.classList.remove('split-left', 'split-right');
    // Remove mini-headers
    const mh = p.querySelector('.panel-mini-header');
    if (mh) mh.remove();
  });

  // Restore active view to full-width
  activateView(viewState.splitLeft || viewState.activeViewId || 'sensors');
  viewState.splitLeft = null;
  viewState.splitRight = null;
}

function setSplitPanels(leftId, rightId) {
  const container = document.getElementById('views-container');

  // Hide all panels first
  container.querySelectorAll('.view-panel').forEach(p => {
    p.classList.remove('active', 'split-left', 'split-right');
    p.style.display = 'none';
    const mh = p.querySelector('.panel-mini-header');
    if (mh) mh.remove();
  });

  // Show left panel
  const leftPanel = document.getElementById('view-' + leftId);
  if (leftPanel) {
    leftPanel.style.display = '';
    leftPanel.classList.add('active', 'split-left');
    addMiniHeader(leftPanel, leftId);
    const leftView = viewState.views.find(v => v.id === leftId);
    if (leftView && leftView.type === 'iframe') lazyLoadIframe(leftId, leftView.src);
  }

  // Show right panel
  const rightPanel = document.getElementById('view-' + rightId);
  if (rightPanel) {
    rightPanel.style.display = '';
    rightPanel.classList.add('active', 'split-right');
    addMiniHeader(rightPanel, rightId);
    const rightView = viewState.views.find(v => v.id === rightId);
    if (rightView && rightView.type === 'iframe') lazyLoadIframe(rightId, rightView.src);
  }

  viewState.splitLeft = leftId;
  viewState.splitRight = rightId;
}

function addMiniHeader(panel, currentViewId) {
  const header = document.createElement('div');
  header.className = 'panel-mini-header';

  // View selector dropdown (only split-compatible views)
  const select = document.createElement('select');
  select.className = 'panel-mode-select';
  viewState.views.forEach(v => {
    if (v.split_ok === false) return;
    const opt = document.createElement('option');
    opt.value = v.id;
    opt.textContent = v.label;
    if (v.split_ok === 'partial') opt.textContent += ' *';
    if (v.id === currentViewId) opt.selected = true;
    select.appendChild(opt);
  });
  select.addEventListener('change', () => {
    const side = panel.classList.contains('split-left') ? 'left' : 'right';
    if (side === 'left') {
      setSplitPanels(select.value, viewState.splitRight);
    } else {
      setSplitPanels(viewState.splitLeft, select.value);
    }
  });

  // Maximize button
  const expandBtn = document.createElement('button');
  expandBtn.className = 'panel-expand-btn';
  expandBtn.innerHTML = '&#x26F6;';
  expandBtn.title = 'Maximize';
  expandBtn.addEventListener('click', () => {
    exitSplitMode();
    activateView(currentViewId);
  });

  header.appendChild(select);
  header.appendChild(expandBtn);
  panel.prepend(header);
}
```

**Step 3: Wire up split toggle button**

Find or add the event listener section. After the voice button listener, add:

```javascript
// Split mode toggle
const splitToggle = document.getElementById('split-toggle');
if (splitToggle) {
  splitToggle.addEventListener('click', toggleSplitMode);
}
```

**Step 4: Commit**

```bash
git add web/static/app.js web/templates/index.html
git commit -m "feat: implement split mode with panel divider and mini-headers"
```

---

## Task 6: Implement Immersive Chat Mode

**Files:**
- Modify: `web/static/app.js` (chat mode transitions)
- Modify: `web/static/style.css` (chat mode layout)
- Modify: `web/templates/index.html` (restructure chat panel)

**Step 1: Restructure chat panel HTML**

Replace the existing chat panel (lines 122-131 of index.html) with:

```html
<!-- ─── IMMERSIVE CHAT MODE ─── -->
<div class="chat-mode" id="chat-mode" style="display:none">
  <div class="chat-mode-header">
    <button class="chat-back-btn" id="chat-back-btn" aria-label="Back to dashboard">&larr; Back</button>
    <span class="chat-mode-title">Assistant</span>
    <button class="chat-clear-btn" id="chat-clear-btn" aria-label="Clear chat">Clear</button>
  </div>
  <div class="chat-mode-body">
    <div class="context-strip" id="context-strip">
      <!-- Populated by JS with live sensor chips -->
    </div>
    <div class="chat-messages" id="chat-messages">
      <div class="chat-msg system">Tap a sensor or ask a question</div>
    </div>
  </div>
</div>
```

**Step 2: Add suggestion chips to input bar**

Update the input bar in index.html:

```html
<div class="input-bar" id="input-bar">
  <div class="suggestion-chips" id="suggestion-chips" style="display:none">
    <button class="suggestion-chip" data-msg="What's the air quality?">Air quality?</button>
    <button class="suggestion-chip" data-msg="How's the temperature?">Temperature?</button>
    <button class="suggestion-chip" data-msg="Describe the camera scene">Camera scene?</button>
    <button class="suggestion-chip" data-msg="Is it going to rain?">Rain forecast?</button>
  </div>
  <div class="input-row">
    <button class="mic-btn" id="mic-btn" aria-label="Voice input" title="Tap to speak">&#127908;</button>
    <div class="chat-input-wrap">
      <input type="text" class="chat-input" id="chat-input"
             placeholder="Ask about your environment..."
             autocomplete="off" enterkeyhint="send">
      <button class="send-btn" id="send-btn" aria-label="Send" disabled>&#9654;</button>
    </div>
  </div>
</div>
```

**Step 3: Add chat mode CSS**

Add to `style.css`:

```css
/* ═══════════════════════════════════════
   IMMERSIVE CHAT MODE
   ═══════════════════════════════════════ */

.chat-mode {
  position: absolute;
  inset: 0;
  z-index: 50;
  background: var(--bg-base);
  display: none;
  flex-direction: column;
}

.chat-mode.active {
  display: flex;
}

.chat-mode-header {
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--sp-3);
  flex-shrink: 0;
}

.chat-back-btn {
  border: none;
  background: var(--bg-base);
  box-shadow: var(--neo-out-sm);
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  font-family: inherit;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  touch-action: manipulation;
}

.chat-back-btn:active {
  box-shadow: var(--neo-in-sm);
}

.chat-mode-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.chat-clear-btn {
  border: none;
  background: none;
  font-family: inherit;
  font-size: 12px;
  color: var(--text-dim);
  cursor: pointer;
}

.chat-mode-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* Context strip — live sensor chips (left column) */
.context-strip {
  width: 110px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-2);
  overflow-y: auto;
  scrollbar-width: none;
}

.context-chip {
  background: var(--bg-base);
  box-shadow: var(--neo-out-sm);
  border-radius: var(--radius-sm);
  padding: var(--sp-2);
  text-align: center;
  transition: box-shadow 0.2s var(--ease), transform 0.2s var(--ease);
}

.context-chip.active {
  box-shadow: var(--neo-in-sm);
  transform: scale(1.05);
}

.chip-label {
  display: block;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-dim);
  letter-spacing: 0.5px;
}

.chip-value {
  display: block;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-value);
  font-variant-numeric: tabular-nums;
}

/* Chat messages area */
.chat-mode-body .chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--sp-2) var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

/* Inline live sensor cards in messages */
.inline-sensor {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  background: var(--bg-base);
  box-shadow: var(--neo-out-sm);
  border-radius: var(--radius-sm);
  padding: 2px 8px;
  margin: 2px 0;
  font-size: 13px;
}

.inline-value {
  font-weight: 700;
  color: var(--text-value);
}

.inline-trend {
  font-size: 11px;
  color: var(--text-dim);
}

.inline-trend.up { color: var(--warn); }
.inline-trend.down { color: var(--accent-cool); }

/* Suggestion chips */
.suggestion-chips {
  display: flex;
  gap: var(--sp-1);
  padding: 0 var(--sp-3);
  overflow-x: auto;
  scrollbar-width: none;
  height: 28px;
  align-items: center;
}

.suggestion-chips::-webkit-scrollbar { display: none; }

.suggestion-chip {
  border: none;
  background: var(--bg-base);
  box-shadow: var(--neo-out-sm);
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  font-family: inherit;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
  white-space: nowrap;
  cursor: pointer;
  touch-action: manipulation;
}

.suggestion-chip:active {
  box-shadow: var(--neo-in-sm);
  color: var(--accent-warm);
}

/* Input bar expanded (chat mode) */
.input-bar.expanded {
  flex-direction: column;
  height: 76px;
  padding: var(--sp-1) var(--sp-3);
  gap: var(--sp-1);
}

.input-bar.expanded .suggestion-chips { display: flex; }
.input-bar.expanded .input-row { display: flex; gap: var(--sp-2); align-items: center; flex: 1; width: 100%; }
```

**Step 4: Add chat mode JS logic**

In `app.js`, add the chat mode manager:

```javascript
// ─── Chat Mode (Immersive) ───

let chatIdleTimer = null;
const CHAT_IDLE_TIMEOUT = 45000; // 45s

function enterChatMode(focusSensor) {
  const chatMode = document.getElementById('chat-mode');
  const inputBar = document.getElementById('input-bar');
  const chipsEl = document.getElementById('suggestion-chips');
  if (!chatMode) return;

  // Show chat mode overlay
  chatMode.style.display = 'flex';
  chatMode.classList.add('active');
  state.chatOpen = true;

  // Expand input bar
  if (inputBar) inputBar.classList.add('expanded');
  if (chipsEl) chipsEl.style.display = '';

  // Build context strip with live sensor data
  buildContextStrip(focusSensor);

  // Start idle timer
  resetChatIdleTimer();

  // Scroll to latest messages
  scrollChat();
}

function exitChatMode() {
  const chatMode = document.getElementById('chat-mode');
  const inputBar = document.getElementById('input-bar');
  const chipsEl = document.getElementById('suggestion-chips');
  if (!chatMode) return;

  chatMode.style.display = 'none';
  chatMode.classList.remove('active');
  state.chatOpen = false;

  if (inputBar) inputBar.classList.remove('expanded');
  if (chipsEl) chipsEl.style.display = 'none';

  if (chatIdleTimer) {
    clearTimeout(chatIdleTimer);
    chatIdleTimer = null;
  }
}

function resetChatIdleTimer() {
  if (chatIdleTimer) clearTimeout(chatIdleTimer);
  chatIdleTimer = setTimeout(() => {
    if (!state.streaming) exitChatMode();
  }, CHAT_IDLE_TIMEOUT);
}

function buildContextStrip(focusSensor) {
  const strip = document.getElementById('context-strip');
  if (!strip) return;
  strip.innerHTML = '';

  const fields = ['temperature', 'humidity', 'voc_index', 'uvi'];

  // If a specific sensor was tapped, put it first
  if (focusSensor && fields.includes(focusSensor)) {
    fields.splice(fields.indexOf(focusSensor), 1);
    fields.unshift(focusSensor);
  }

  fields.forEach(field => {
    const data = state.sensors[field];
    const chip = document.createElement('div');
    chip.className = 'context-chip' + (field === focusSensor ? ' active' : '');
    chip.dataset.field = field;

    const label = document.createElement('span');
    label.className = 'chip-label';
    label.textContent = SENSOR_MAP[field]?.label || field;

    const value = document.createElement('span');
    value.className = 'chip-value';
    value.id = 'ctx-' + field;
    value.textContent = data ? formatSensorValue(field, data.value) : '--';

    chip.appendChild(label);
    chip.appendChild(value);
    strip.appendChild(chip);
  });
}

function updateContextStrip() {
  // Called during sensor updates to keep context chips live
  const strip = document.getElementById('context-strip');
  if (!strip || !state.chatOpen) return;

  strip.querySelectorAll('.context-chip').forEach(chip => {
    const field = chip.dataset.field;
    const data = state.sensors[field];
    const valEl = chip.querySelector('.chip-value');
    if (valEl && data) {
      valEl.textContent = formatSensorValue(field, data.value);
    }
  });
}
```

**Step 5: Wire up chat mode triggers**

Replace the existing `showChatPanel`/`hideChatPanel` calls. Find where sensor cards get click listeners and update to trigger chat mode:

```javascript
// Sensor cards → enter chat mode with that sensor focused
sensorGrid.addEventListener('click', (e) => {
  const card = e.target.closest('.sensor-card');
  if (!card) return;
  const sensor = card.dataset.sensor;
  if (sensor === 'camera' || sensor === 'weather' || sensor === 'comfort') return;
  enterChatMode(sensor);
  // Auto-ask about that sensor
  const label = SENSOR_MAP[sensor]?.label || sensor;
  chatInput.value = `How's the ${label.toLowerCase()}?`;
  chatInput.focus();
});

// Back button
const chatBackBtn = document.getElementById('chat-back-btn');
if (chatBackBtn) chatBackBtn.addEventListener('click', exitChatMode);

// Clear button
const chatClearBtn = document.getElementById('chat-clear-btn');
if (chatClearBtn) chatClearBtn.addEventListener('click', () => {
  state.messages = [];
  localStorage.removeItem(CHAT_STORAGE_KEY);
  const messagesEl = document.getElementById('chat-messages');
  if (messagesEl) messagesEl.innerHTML = '<div class="chat-msg system">Tap a sensor or ask a question</div>';
});

// Input focus → enter chat mode
chatInput.addEventListener('focus', () => {
  if (!state.chatOpen) enterChatMode(null);
  resetChatIdleTimer();
});

// Suggestion chips
document.querySelectorAll('.suggestion-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    const msg = chip.dataset.msg;
    if (msg) {
      chatInput.value = msg;
      sendBtn.disabled = false;
      sendBtn.click();
    }
  });
});

// Reset idle timer on any interaction
['click', 'touchstart', 'keydown'].forEach(evt => {
  document.addEventListener(evt, () => {
    if (state.chatOpen) resetChatIdleTimer();
  }, { passive: true });
});
```

**Step 6: Update sensor update function to also update context strip**

In the `updateSensor()` function, at the end (after updating DOM cards), add:

```javascript
updateContextStrip();
```

**Step 7: Commit**

```bash
git add web/static/app.js web/static/style.css web/templates/index.html
git commit -m "feat: implement immersive chat mode with context strip and suggestion chips"
```

---

## Task 7: Deploy and Test

**Files:**
- No code changes — deployment and verification

**Step 1: Deploy to Pi**

```bash
bash deploy.sh && bash deploy.sh --service restart
```

Expected: Code syncs via rsync, service restarts, browser refreshes.

**Step 2: Verify view switching**

Open browser at `http://192.168.0.228:5000`. You should see:
- Header with view tab chips (Sensors, Earth, Quakes, etc.)
- Sensor grid as default view
- Tapping a tab switches to that view
- Iframe views lazy-load on first tap
- Split toggle button in header status area

**Step 3: Verify split mode**

Tap the split toggle (&#9638;). You should see:
- Two panels side by side with 24px divider
- Mini-headers with dropdown selectors
- Only split-compatible views in dropdowns
- Maximize button returns to full-width

**Step 4: Verify chat mode**

Tap the chat input or a sensor card. You should see:
- Dashboard morphs to show context strip (left) + chat (right)
- Suggestion chips appear above input
- "Back" button in header returns to dashboard
- 45s idle timeout auto-exits chat mode
- Context strip shows live sensor values

**Step 5: Commit and tag**

```bash
git add -A && git commit -m "chore: post-deployment verification"
git tag v5.0.0-kiosk -m "Multi-view kiosk with immersive chat"
```

---

## Summary of Changes

| File | Action | What |
|------|--------|------|
| `dashboard.yaml` | Append | Views registry section (13 views) |
| `web_app.py` | Add route | `/api/views` endpoint |
| `web/templates/index.html` | Restructure | View tabs in header, views container, chat mode panel, suggestion chips |
| `web/static/style.css` | Add sections | View tabs, views container, split mode, chat mode, suggestion chips, context strip |
| `web/static/app.js` | Add modules | ViewManager (tabs, iframes, LRU), split mode, chat mode, context strip, suggestion chips |

**Total new CSS**: ~250 lines
**Total new JS**: ~300 lines
**Total tasks**: 7 (config → HTML → CSS → JS views → JS split → JS chat → deploy)
