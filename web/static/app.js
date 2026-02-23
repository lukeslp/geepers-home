/* Observatory — client-side dashboard logic
   Connects to Flask SSE for sensor data, proxies chat to VPS LLM */

(function () {
  'use strict';

  // ─── State ───
  const state = {
    sensors: {},           // latest readings keyed by field name
    history: {},           // last N values per sensor for trends
    weather: null,         // latest weather data from WeatherSource
    headlines: [],         // news headlines from NYT
    headlineIndex: 0,      // current headline rotation index
    lastDataTime: 0,       // timestamp of last SSE sensor event
    scene: '',             // latest camera scene description
    messages: [],          // chat history
    streaming: false,      // currently receiving LLM response
    chatOpen: false,       // chat mode active
    systemStats: {},       // latest system.stats SSE data
    networkStats: {},      // latest net.health SSE data
    activeAlerts: [],      // currently active threshold alerts
    // View system
    views: [],             // view definitions from /api/views
    activeView: 'home',    // currently shown view id
    splitMode: false,      // split-panel mode active
    splitLeft: 'home',     // left panel view id
    splitRight: null,      // right panel view id
    splitRatio: 0,         // 0=50/50, 1=65/35, 2=35/65
    iframeOrder: [],       // LRU order of loaded iframe view ids
  };

  const HISTORY_LEN = 20;
  const CHAT_STORAGE_KEY = 'geepers_chat';
  const CHAT_MAX_STORED = 20;
  const MAX_IFRAMES = 3;         // LRU limit for Pi memory
  const CHAT_IDLE_TIMEOUT = 45000; // 45s idle → exit chat mode

  // Human-readable labels for all known sensor fields
  const SENSOR_LABELS = {
    temperature: 'Temperature',
    humidity: 'Humidity',
    pressure: 'Pressure',
    uvi: 'UV Index',
    voc_index: 'Air Quality',
    uva: 'UV-A Raw',
    cpu_temp: 'CPU Temp',
    ram: 'RAM Usage',
    disk: 'Disk Usage',
  };

  // WMO weather codes → text icons (no emoji font on Pi)
  const WEATHER_ICONS = {
    clear: { day: '\u2600', night: '\u263E' },           // ☀ ☾
    partly_cloudy: { day: '\u26C5', night: '\u26C5' },   // ⛅
    cloudy: { day: '\u2601', night: '\u2601' },           // ☁
    fog: { day: '\u2592', night: '\u2592' },              // ▒
    drizzle: { day: '\u2602', night: '\u2602' },          // ☂
    rain: { day: '\u2602', night: '\u2602' },             // ☂
    snow: { day: '\u2744', night: '\u2744' },             // ❄
    showers: { day: '\u2602', night: '\u2602' },          // ☂
    thunderstorm: { day: '\u26A1', night: '\u26A1' },     // ⚡
  };

  // ─── DOM refs ───
  const body = document.body;
  const dashboard = document.getElementById('dashboard');
  const clockEl = document.getElementById('clock');
  const statusDot = document.getElementById('status-dot');
  const sensorCount = document.getElementById('sensor-count');
  const chatMessages = document.getElementById('chat-messages');
  const chatInput = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');
  const sensorGrid = document.getElementById('sensor-grid');
  const cameraCard = document.getElementById('camera-card');
  const cameraThumb = document.getElementById('camera-thumb');
  // View system refs
  const viewTabs = document.getElementById('view-tabs');
  const viewsContainer = document.getElementById('views-container');
  const splitToggle = document.getElementById('split-toggle');
  const chatBackBtn = document.getElementById('chat-back-btn');
  const chatMode = document.getElementById('chat-mode');
  const contextStrip = document.getElementById('context-strip');
  const suggestionChips = document.getElementById('suggestion-chips');
  const panelDivider = document.getElementById('panel-divider');

  // Comfort card elements
  const comfortArcFill = document.getElementById('comfort-arc-fill');
  const comfortScore = document.getElementById('comfort-score');
  const comfortLabel = document.getElementById('comfort-label');

  // Radio badge elements
  const wifiBadge = document.getElementById('wifi-count');
  const bleBadge = document.getElementById('ble-count');

  // News ticker elements
  const tickerSection = document.getElementById('ticker-section');
  const tickerHeadline = document.getElementById('ticker-headline');
  const newsTicker = document.getElementById('news-ticker');

  // Voice button
  const micBtn = document.getElementById('mic-btn');

  // Weather card elements
  const weatherIcon = document.getElementById('weather-icon');
  const weatherDesc = document.getElementById('weather-desc');
  const outdoorTemp = document.getElementById('outdoor-temp');
  const outdoorHumid = document.getElementById('outdoor-humid');
  const indoorTemp = document.getElementById('indoor-temp');
  const indoorHumid = document.getElementById('indoor-humid');
  const weatherWind = document.getElementById('weather-wind');
  const weatherFeels = document.getElementById('weather-feels');

  // ─── Clock ───
  function updateClock() {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    clockEl.textContent = `${h}:${m}`;
  }
  setInterval(updateClock, 10000);
  updateClock();

  // ─── View System ───
  let chatIdleTimer = null;

  async function loadViews() {
    try {
      const resp = await fetch('/api/views');
      if (!resp.ok) return;
      const data = await resp.json();
      state.views = data.views || [];
    } catch {
      state.views = [{ id: 'home', label: 'Home', type: 'native', default: true }];
    }
    buildViewTabs();
    // Activate default view
    const defaultView = state.views.find(v => v.default) || state.views[0];
    if (defaultView) activateView(defaultView.id);
  }

  function buildViewTabs() {
    if (!viewTabs) return;
    viewTabs.innerHTML = '';
    state.views.forEach(view => {
      const btn = document.createElement('button');
      btn.className = 'view-tab';
      btn.textContent = view.label;
      btn.dataset.viewId = view.id;
      btn.addEventListener('click', () => {
        if (state.chatOpen) exitChatMode();
        activateView(view.id);
      });
      viewTabs.appendChild(btn);
    });
  }

  function activateView(viewId) {
    if (state.splitMode) return; // Split mode uses its own panel management

    // Chat tab triggers chat mode instead of a panel switch
    if (viewId === 'chat') {
      enterChatMode();
      return;
    }

    // Exit chat mode if switching to a non-chat view
    if (state.chatOpen) exitChatMode();

    state.activeView = viewId;

    // Update tab active states
    viewTabs.querySelectorAll('.view-tab').forEach(tab => {
      tab.classList.toggle('active', tab.dataset.viewId === viewId);
    });

    // Hide all view panels
    viewsContainer.querySelectorAll('.view-panel').forEach(p => {
      p.classList.remove('active');
    });

    const view = state.views.find(v => v.id === viewId);
    if (!view) return;

    if (view.type === 'native') {
      const panel = document.getElementById('view-' + viewId);
      if (panel) panel.classList.add('active');
      // Populate dynamic panels on activation
      if (viewId === 'news') populateNewsFeed();
      if (viewId === 'environment') populateEnvironmentGrid();
      if (viewId === 'system') populateSystemGrid();
    } else if (view.type === 'iframe') {
      let panel = document.getElementById('view-' + viewId);
      if (!panel) {
        panel = createIframePanel(view);
        viewsContainer.appendChild(panel);
      }
      panel.classList.add('active');
      lazyLoadIframe(view);
    }
  }

  function createIframePanel(view) {
    const panel = document.createElement('div');
    panel.className = 'view-panel';
    panel.id = 'view-' + view.id;
    panel.dataset.view = view.id;
    // Iframe created on demand by lazyLoadIframe
    return panel;
  }

  function lazyLoadIframe(view) {
    const panel = document.getElementById('view-' + view.id);
    if (!panel) return;

    // Check if already has an iframe
    let iframe = panel.querySelector('iframe');
    if (iframe) {
      // Already loaded, just update LRU order
      touchIframeLRU(view.id);
      return;
    }

    // Enforce LRU limit — evict oldest if at max
    while (state.iframeOrder.length >= MAX_IFRAMES) {
      const evictId = state.iframeOrder.shift();
      evictIframe(evictId);
    }

    // Create and load iframe
    iframe = document.createElement('iframe');
    iframe.src = view.src;
    iframe.loading = 'lazy';
    iframe.sandbox = 'allow-scripts allow-same-origin allow-popups';
    panel.appendChild(iframe);

    // Track in LRU
    state.iframeOrder.push(view.id);
  }

  function touchIframeLRU(viewId) {
    const idx = state.iframeOrder.indexOf(viewId);
    if (idx > -1) state.iframeOrder.splice(idx, 1);
    state.iframeOrder.push(viewId);
  }

  function evictIframe(viewId) {
    const panel = document.getElementById('view-' + viewId);
    if (!panel) return;
    const iframe = panel.querySelector('iframe');
    if (iframe) {
      iframe.src = 'about:blank';
      iframe.remove();
    }
  }

  // ─── Split Mode ───
  function toggleSplitMode() {
    state.splitMode = !state.splitMode;
    if (splitToggle) splitToggle.classList.toggle('active', state.splitMode);

    if (state.splitMode) {
      // Enter split mode
      if (state.chatOpen) exitChatMode();
      viewsContainer.classList.add('split-mode');
      panelDivider.style.display = '';
      state.splitLeft = state.activeView;
      // Pick a sensible default for right panel
      const other = state.views.find(v => v.id !== state.activeView && v.split_ok !== false);
      state.splitRight = other ? other.id : state.views[0].id;
      state.splitRatio = 0;
      applySplitPanels();
    } else {
      // Exit split mode
      viewsContainer.classList.remove('split-mode');
      panelDivider.style.display = 'none';
      viewsContainer.querySelectorAll('.view-panel').forEach(p => {
        p.classList.remove('split-left', 'split-right', 'active');
      });
      activateView(state.splitLeft || state.activeView);
    }
  }

  function applySplitPanels() {
    viewsContainer.querySelectorAll('.view-panel').forEach(p => {
      p.classList.remove('split-left', 'split-right', 'active');
    });

    [state.splitLeft, state.splitRight].forEach((viewId, idx) => {
      if (!viewId) return;
      const view = state.views.find(v => v.id === viewId);
      if (!view) return;
      let panel = document.getElementById('view-' + viewId);
      if (!panel && view.type === 'iframe') {
        panel = createIframePanel(view);
        viewsContainer.appendChild(panel);
      }
      if (!panel) return;
      panel.classList.add(idx === 0 ? 'split-left' : 'split-right');
      if (view.type === 'iframe') lazyLoadIframe(view);
    });

    // Apply ratio
    const ratios = ['1fr 24px 1fr', '1.85fr 24px 1fr', '1fr 24px 1.85fr'];
    viewsContainer.style.gridTemplateColumns = ratios[state.splitRatio] || ratios[0];
  }

  function cycleSplitRatio() {
    state.splitRatio = (state.splitRatio + 1) % 3;
    const ratios = ['1fr 24px 1fr', '1.85fr 24px 1fr', '1fr 24px 1.85fr'];
    viewsContainer.style.gridTemplateColumns = ratios[state.splitRatio];
  }

  if (splitToggle) {
    splitToggle.addEventListener('click', toggleSplitMode);
  }
  if (panelDivider) {
    panelDivider.addEventListener('click', cycleSplitRatio);
  }

  // ─── Chat Mode (immersive) ───
  function enterChatMode() {
    if (state.chatOpen) return;
    state.chatOpen = true;
    if (chatMode) chatMode.style.display = 'grid';
    if (dashboard) dashboard.classList.add('chat-active');
    if (suggestionChips) suggestionChips.style.display = 'flex';
    if (chatBackBtn) chatBackBtn.style.display = '';
    // Highlight chat tab if it exists
    viewTabs.querySelectorAll('.view-tab').forEach(tab => {
      tab.classList.toggle('active', tab.dataset.viewId === 'chat');
    });
    buildContextStrip();
    scrollChat();
    resetChatIdleTimer();
    chatInput.focus();
  }

  function exitChatMode() {
    if (!state.chatOpen) return;
    state.chatOpen = false;
    if (chatMode) chatMode.style.display = 'none';
    if (dashboard) dashboard.classList.remove('chat-active');
    if (suggestionChips) suggestionChips.style.display = 'none';
    if (chatBackBtn) chatBackBtn.style.display = 'none';
    // Restore view tabs
    if (viewTabs) viewTabs.style.display = 'flex';
    if (splitToggle) splitToggle.style.display = '';
    clearChatIdleTimer();
    // Re-activate previous view (default to home)
    const restoreView = state.activeView !== 'chat' ? state.activeView : 'home';
    activateView(restoreView);
  }

  function buildContextStrip() {
    if (!contextStrip) return;
    contextStrip.innerHTML = '';
    // Add sensor chips for live data
    const chipFields = ['temperature', 'humidity', 'voc_index', 'uvi'];
    chipFields.forEach(field => {
      const meta = SENSOR_MAP[field];
      if (!meta) return;
      const chip = document.createElement('div');
      chip.className = 'context-chip';
      chip.dataset.field = field;
      const label = SENSOR_LABELS[field] || field;
      const value = state.sensors[field];
      const formatted = value != null ? meta.fmt(value) : '--';
      chip.innerHTML = `<span class="chip-label">${label}</span><span class="chip-value">${formatted}<span style="font-size:10px;color:var(--text-dim)">${meta.unit}</span></span>`;
      chip.addEventListener('click', () => {
        chip.classList.toggle('active');
        if (value != null) {
          sendMessage(`Tell me about the ${label} reading of ${meta.fmt(value)}${meta.unit}`);
        }
      });
      contextStrip.appendChild(chip);
    });

    // Weather chip
    if (state.weather) {
      const wChip = document.createElement('div');
      wChip.className = 'context-chip';
      wChip.innerHTML = `<span class="chip-label">Outdoor</span><span class="chip-value">${state.weather.weather_desc || '--'}</span>`;
      wChip.addEventListener('click', () => {
        sendMessage('Compare the indoor and outdoor conditions.');
      });
      contextStrip.appendChild(wChip);
    }
  }

  function updateContextStrip() {
    if (!contextStrip || !state.chatOpen) return;
    contextStrip.querySelectorAll('.context-chip').forEach(chip => {
      const field = chip.dataset.field;
      if (!field) return;
      const meta = SENSOR_MAP[field];
      if (!meta) return;
      const value = state.sensors[field];
      const valueEl = chip.querySelector('.chip-value');
      if (valueEl && value != null) {
        valueEl.innerHTML = `${meta.fmt(value)}<span style="font-size:10px;color:var(--text-dim)">${meta.unit}</span>`;
      }
    });
  }

  // Chat idle timer — auto-exit after inactivity
  function resetChatIdleTimer() {
    clearChatIdleTimer();
    chatIdleTimer = setTimeout(() => {
      if (state.chatOpen && !state.streaming) exitChatMode();
    }, CHAT_IDLE_TIMEOUT);
  }

  function clearChatIdleTimer() {
    if (chatIdleTimer) {
      clearTimeout(chatIdleTimer);
      chatIdleTimer = null;
    }
  }

  if (chatBackBtn) {
    chatBackBtn.addEventListener('click', exitChatMode);
  }

  // Suggestion chip handlers
  if (suggestionChips) {
    suggestionChips.addEventListener('click', (e) => {
      const chip = e.target.closest('.chip');
      if (!chip) return;
      const query = chip.dataset.q;
      if (query) sendMessage(query);
    });
  }

  // ─── View panel population ───

  function populateNewsFeed() {
    const container = document.getElementById('news-feed');
    if (!container) return;
    if (state.headlines.length === 0) {
      container.innerHTML = '<div class="chat-msg system">No headlines yet. Waiting for news feed...</div>';
      return;
    }
    container.innerHTML = state.headlines.map(h =>
      `<div class="news-item">
        <span class="news-section">${h.section || ''}</span>
        <a class="news-title" href="${h.url || '#'}" target="_blank" rel="noopener">${h.title || ''}</a>
        ${h.abstract ? `<span class="news-abstract">${h.abstract}</span>` : ''}
      </div>`
    ).join('');
  }

  function populateEnvironmentGrid() {
    const container = document.getElementById('environment-grid');
    if (!container) return;
    const fields = Object.keys(SENSOR_MAP);
    if (fields.length === 0) {
      container.innerHTML = '<div class="chat-msg system">Waiting for sensor data...</div>';
      return;
    }
    container.innerHTML = fields.map(field => {
      const meta = SENSOR_MAP[field];
      const value = state.sensors[field];
      const formatted = value != null ? meta.fmt(value) : '--';
      const label = SENSOR_LABELS[field] || field;
      const hist = state.history[field] || [];
      let trendHtml = '<span class="sensor-trend trend-stable">&#9679; waiting</span>';
      if (hist.length >= 3) {
        const recent = hist.slice(-3);
        const avg = recent.reduce((a, b) => a + b, 0) / recent.length;
        const older = hist.slice(0, Math.max(1, hist.length - 3));
        const oldAvg = older.reduce((a, b) => a + b, 0) / older.length;
        const diff = avg - oldAvg;
        const pct = oldAvg !== 0 ? Math.abs(diff / oldAvg) * 100 : 0;
        if (pct > 2) {
          const dir = diff > 0 ? 'up' : 'down';
          trendHtml = `<span class="sensor-trend trend-${dir}">${dir === 'up' ? '&#9650;' : '&#9660;'} ${dir === 'up' ? 'rising' : 'falling'}</span>`;
        } else {
          trendHtml = '<span class="sensor-trend trend-stable">&#9679; stable</span>';
        }
      }
      return `<div class="sensor-card" data-sensor="${field}">
        <span class="sensor-label">${label}</span>
        <span class="sensor-value">${formatted}<span class="sensor-unit">${meta.unit}</span></span>
        ${trendHtml}
      </div>`;
    }).join('');

    // Tap to ask about a sensor
    container.querySelectorAll('.sensor-card').forEach(card => {
      card.addEventListener('click', () => {
        const field = card.dataset.sensor;
        const meta = SENSOR_MAP[field];
        const value = state.sensors[field];
        if (value != null && meta) {
          sendMessage(`Tell me about the ${SENSOR_LABELS[field] || field} reading of ${meta.fmt(value)}${meta.unit}`);
        }
      });
    });
  }

  function populateSystemGrid() {
    const container = document.getElementById('system-grid');
    if (!container) return;
    // System data comes from SSE system.stats topic, stored in state
    const sys = state.systemStats || {};
    const net = state.networkStats || {};

    const cards = [];

    function barColor(pct) {
      if (pct < 60) return 'var(--good)';
      if (pct < 80) return 'var(--warn)';
      return 'var(--alert)';
    }

    function barHtml(pct) {
      return `<div class="sys-bar"><div class="sys-bar-fill" style="width:${pct}%;background:${barColor(pct)}"></div></div>`;
    }

    // CPU temp
    if (sys.cpu_temp != null) {
      const pct = Math.min(100, Math.max(0, (sys.cpu_temp / 85) * 100));
      cards.push({ label: 'CPU Temp', value: sys.cpu_temp.toFixed(1) + '\u00b0C', bar: barHtml(pct) });
    }
    // CPU load
    if (sys.load_1m != null) {
      const pct = Math.min(100, Math.max(0, (sys.load_1m / 4) * 100));
      cards.push({ label: 'Load', value: sys.load_1m.toFixed(2), bar: barHtml(pct) });
    }
    // RAM
    if (sys.ram_percent != null) {
      cards.push({ label: 'Memory', value: sys.ram_percent.toFixed(0) + '%', bar: barHtml(sys.ram_percent) });
    }
    // Disk
    if (sys.disk_percent != null) {
      cards.push({ label: 'Disk', value: sys.disk_percent.toFixed(0) + '%', bar: barHtml(sys.disk_percent) });
    }
    // Uptime
    if (sys.uptime_str) {
      cards.push({ label: 'Uptime', value: sys.uptime_str });
    }
    // IP address
    if (net.ip) {
      cards.push({ label: 'IP Address', value: net.ip });
    }
    // Ping
    if (net.ping_ms != null) {
      cards.push({ label: 'Ping', value: net.ping_ms.toFixed(0) + 'ms' });
    }
    // WiFi
    if (state.radioWifi) {
      const count = state.radioWifi.network_count || 0;
      const ssid = state.radioWifi.connected_ssid || 'N/A';
      cards.push({ label: 'WiFi', value: `${ssid} (${count} nearby)` });
    }
    // BLE
    if (state.radioBle) {
      const count = state.radioBle.total_count || state.radioBle.ble_device_count || 0;
      cards.push({ label: 'Bluetooth', value: `${count} devices` });
    }

    if (cards.length === 0) {
      container.innerHTML = '<div class="chat-msg system">Waiting for system data...</div>';
      return;
    }

    container.innerHTML = cards.map(c =>
      `<div class="sensor-card">
        <span class="sensor-label">${c.label}</span>
        <span class="sensor-value">${c.value}</span>
        ${c.bar || ''}
      </div>`
    ).join('');
  }

  // ─── Camera thumbnail polling ───
  let cameraThumbInterval = null;

  function startCameraThumbPolling() {
    if (cameraThumbInterval || !cameraThumb) return;
    refreshCameraThumb();
    cameraThumbInterval = setInterval(refreshCameraThumb, 5000);
  }

  function refreshCameraThumb() {
    if (!cameraThumb) return;
    cameraThumb.src = '/api/camera/frame?t=' + Date.now();
  }

  // Start thumb polling after a short delay
  setTimeout(startCameraThumbPolling, 2000);

  // ─── Sensor count button → all sensors overlay ───
  if (sensorCount) {
    sensorCount.addEventListener('click', () => {
      showAllSensors();
    });
  }

  // ─── SSE: Sensor data stream ───
  let sseRetryCount = 0;

  function connectSSE() {
    const evtSource = new EventSource('/api/sensors/stream');

    evtSource.onopen = () => {
      statusDot.className = 'dot';
      sseRetryCount = 0;
    };

    evtSource.addEventListener('sensor', (e) => {
      try {
        const data = JSON.parse(e.data);
        updateSensor(data);
      } catch (err) {
        console.warn('Bad sensor event:', err);
      }
    });

    evtSource.addEventListener('vision', (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.description) {
          state.scene = data.description;
          // Update camera overlay description if it exists
          const descEl = document.getElementById('camera-description');
          if (descEl) descEl.textContent = data.description;
        }
      } catch (err) {
        console.warn('Bad vision event:', err);
      }
    });

    evtSource.addEventListener('alert', (e) => {
      try {
        const alert = JSON.parse(e.data);
        showAlertToast(alert);
        // Keep last 10 alerts for LLM context
        state.activeAlerts.push(alert);
        if (state.activeAlerts.length > 10) state.activeAlerts.shift();
      } catch (err) {
        console.warn('Bad alert event:', err);
      }
    });

    evtSource.addEventListener('voice', (e) => {
      try {
        const data = JSON.parse(e.data);
        updateVoiceState(data.state || 'idle');
      } catch (err) {
        console.warn('Bad voice event:', err);
      }
    });

    evtSource.addEventListener('weather', (e) => {
      try {
        const data = JSON.parse(e.data);
        updateWeather(data);
      } catch (err) {
        console.warn('Bad weather event:', err);
      }
    });

    evtSource.addEventListener('news', (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.headlines && data.headlines.length > 0) {
          state.headlines = data.headlines;
          state.headlineIndex = 0;
          updateHeadline();
          if (state.activeView === 'news') populateNewsFeed();
        }
      } catch (err) {
        console.warn('Bad news event:', err);
      }
    });

    evtSource.onerror = () => {
      statusDot.className = 'dot warn';
      evtSource.close();
      sseRetryCount++;
      const delay = Math.min(1000 * Math.pow(2, sseRetryCount), 30000);
      setTimeout(connectSSE, delay);
    };
  }

  // ─── Sensor config (loaded from /api/config, replaces hardcoded map) ───
  let SENSOR_MAP = {};

  // Converters for special transforms (e.g. Celsius → Fahrenheit)
  const CONVERTERS = {
    c_to_f: v => v * 9/5 + 32,
  };

  // Build a formatter from a Python-style format string
  function makeFormatter(fmt, convert) {
    const converter = convert ? (CONVERTERS[convert] || (v => v)) : (v => v);
    // Parse Python format: {:.1f} → 1 decimal, {:.0f} → 0 decimals
    const match = fmt.match(/\{:?\.?(\d+)?f?\}/);
    const decimals = match && match[1] !== undefined ? parseInt(match[1]) : 1;
    return v => converter(v).toFixed(decimals);
  }

  // Map threshold colors to semantic status
  function colorToStatus(color) {
    if (!color) return 'good';
    const c = color.toLowerCase();
    if (c.includes('ff5252') || c.includes('d45a5a')) return 'alert';
    if (c.includes('ffa726') || c.includes('ff9100') || c.includes('d4953a')) return 'warn';
    if (c.includes('707070') || c.includes('a0a0a0')) return 'dim';
    return 'good';
  }

  async function loadConfig() {
    try {
      const resp = await fetch('/api/config');
      if (!resp.ok) return;
      const config = await resp.json();

      Object.entries(config.sensors || {}).forEach(([field, meta]) => {
        SENSOR_MAP[field] = {
          unit: meta.unit || '',
          fmt: makeFormatter(meta.format || '{:.1f}', meta.convert),
          thresholds: (meta.thresholds || []).map(([val, color]) => [val, colorToStatus(color)]),
        };
      });
    } catch (err) {
      console.warn('Failed to load sensor config, using defaults:', err);
      // Fallback defaults so the dashboard still works
      SENSOR_MAP = {
        temperature: { unit: '\u00b0F', fmt: v => (v * 9/5 + 32).toFixed(1), thresholds: [[59,'good'],[72,'good'],[82,'warn'],[210,'alert']] },
        humidity:    { unit: '%',   fmt: v => v.toFixed(0), thresholds: [[30,'warn'],[50,'good'],[70,'warn'],[100,'alert']] },
        voc_index:   { unit: ' VOC',fmt: v => v.toFixed(0), thresholds: [[100,'good'],[150,'warn'],[250,'warn'],[500,'alert']] },
        pressure:    { unit: ' hPa',fmt: v => v.toFixed(0), thresholds: [] },
        uvi:         { unit: '',    fmt: v => v.toFixed(1), thresholds: [[2,'good'],[5,'warn'],[7,'warn'],[99,'alert']] },
      };
    }
  }

  function updateSensor(data) {
    // data comes as flat payload: { _topic, temperature, humidity, lux, ... }
    const readings = data.readings || data;

    // Handle radio scanner data (WiFi / BLE badges)
    const topic = readings._topic || '';
    if (topic === 'radio.wifi') {
      state.radioWifi = readings;
      const count = readings.network_count;
      if (count != null && wifiBadge) {
        wifiBadge.textContent = count + ' WiFi';
        wifiBadge.classList.add('active');
        wifiBadge.title = readings.connected_ssid
          ? `Connected: ${readings.connected_ssid} (${readings.connected_signal} dBm) | ${count} networks — tap for details`
          : `${count} WiFi networks nearby — tap for details`;
      }
      return; // Don't process as regular sensor
    }
    if (topic === 'radio.ble') {
      state.radioBle = readings;
      const count = readings.total_count || readings.ble_device_count || 0;
      if (bleBadge) {
        bleBadge.textContent = count + ' BLE';
        bleBadge.classList.add('active');
        const names = (readings.device_names || []).slice(0, 3).join(', ');
        bleBadge.title = names ? `${count} devices: ${names} — tap for details` : `${count} Bluetooth devices — tap for details`;
      }
      return; // Don't process as regular sensor
    }

    // Capture system stats for System view
    if (topic === 'system.stats') {
      state.systemStats = readings;
      if (state.activeView === 'system') populateSystemGrid();
      // Don't return — cpu_temp etc. may also be in SENSOR_MAP
    }
    if (topic === 'net.health') {
      state.networkStats = readings;
      if (state.activeView === 'system') populateSystemGrid();
    }

    // Extract any field that matches SENSOR_MAP

    Object.entries(readings).forEach(([field, value]) => {
      if (value == null || !(field in SENSOR_MAP) || typeof value !== 'number') return;

      const prev = state.sensors[field];
      state.sensors[field] = value;

      // Track history for trends
      if (!state.history[field]) state.history[field] = [];
      state.history[field].push(value);
      if (state.history[field].length > HISTORY_LEN) state.history[field].shift();

      // Update DOM
      const card = sensorGrid.querySelector(`[data-sensor="${field}"]`);
      if (!card) return;

      // Remove loading state on first data
      card.classList.remove('loading');

      const valueEl = card.querySelector('.sensor-value');
      const trendEl = card.querySelector('.sensor-trend');
      const meta = SENSOR_MAP[field];

      // Format value
      const formatted = meta.fmt(value);
      valueEl.innerHTML = `${formatted}<span class="sensor-unit">${meta.unit}</span>`;

      // Flash on change
      if (prev !== undefined && prev !== value) {
        valueEl.classList.remove('updated');
        void valueEl.offsetWidth; // force reflow
        valueEl.classList.add('updated');
      }

      // Trend arrow
      const hist = state.history[field];
      if (hist.length >= 3) {
        const recent = hist.slice(-3);
        const avg = recent.reduce((a, b) => a + b, 0) / recent.length;
        const older = hist.slice(0, Math.max(1, hist.length - 3));
        const oldAvg = older.reduce((a, b) => a + b, 0) / older.length;
        const diff = avg - oldAvg;
        const pct = oldAvg !== 0 ? Math.abs(diff / oldAvg) * 100 : 0;

        if (pct > 2) {
          const dir = diff > 0 ? 'up' : 'down';
          trendEl.className = `sensor-trend trend-${dir}`;
          trendEl.innerHTML = `${dir === 'up' ? '&#9650;' : '&#9660;'} ${dir === 'up' ? 'rising' : 'falling'}`;
        } else {
          trendEl.className = 'sensor-trend trend-stable';
          trendEl.innerHTML = '&#9679; stable';
        }
      }

      // Status color via thresholds
      if (meta.thresholds.length > 0) {
        card.classList.remove('alert');
        for (const [threshold, status] of meta.thresholds) {
          if (value <= threshold) {
            if (status === 'alert') card.classList.add('alert');
            break;
          }
        }
      }
    });

    // Track last data timestamp for freshness indicator
    state.lastDataTime = Date.now();

    // Update indoor readings on weather card
    if (readings.temperature != null && state.sensors.temperature != null) {
      const tempMeta = SENSOR_MAP.temperature;
      if (tempMeta && indoorTemp) {
        indoorTemp.innerHTML = tempMeta.fmt(state.sensors.temperature) + '<span class="weather-unit">' + tempMeta.unit + '</span>';
      }
    }
    if (readings.humidity != null && state.sensors.humidity != null) {
      if (indoorHumid) {
        indoorHumid.textContent = Math.round(state.sensors.humidity) + '%';
      }
    }

    // Update freshness display
    updateFreshness();

    // Recompute comfort score on each sensor update
    computeComfortScore();

    // Keep chat mode context strip in sync with live data
    updateContextStrip();
  }

  // ─── Weather card update ───
  function updateWeather(data) {
    state.weather = data;

    // Icon
    const iconKey = data.weather_icon || 'clear';
    const isDay = data.is_day !== 0;
    const iconSet = WEATHER_ICONS[iconKey] || WEATHER_ICONS.clear;
    weatherIcon.textContent = isDay ? iconSet.day : iconSet.night;

    // Description
    weatherDesc.textContent = data.weather_desc || '';

    // Outdoor temp (convert C → F if config says so)
    const outdoorC = data.outdoor_temp;
    if (outdoorC != null) {
      const tempMeta = SENSOR_MAP.temperature;
      if (tempMeta) {
        outdoorTemp.innerHTML = tempMeta.fmt(outdoorC) + '<span class="weather-unit">' + tempMeta.unit + '</span>';
      } else {
        outdoorTemp.textContent = outdoorC.toFixed(1) + '\u00b0';
      }
    }

    // Outdoor humidity
    if (data.outdoor_humidity != null) {
      outdoorHumid.textContent = Math.round(data.outdoor_humidity) + '%';
    }

    // Indoor values from live sensor state
    if (state.sensors.temperature != null) {
      const tempMeta = SENSOR_MAP.temperature;
      if (tempMeta) {
        indoorTemp.innerHTML = tempMeta.fmt(state.sensors.temperature) + '<span class="weather-unit">' + tempMeta.unit + '</span>';
      }
    }
    if (state.sensors.humidity != null) {
      indoorHumid.textContent = Math.round(state.sensors.humidity) + '%';
    }

    // Wind speed
    if (data.wind_speed != null) {
      weatherWind.textContent = Math.round(data.wind_speed) + ' km/h wind';
    }

    // Feels like
    if (data.feels_like != null) {
      const tempMeta = SENSOR_MAP.temperature;
      if (tempMeta) {
        weatherFeels.textContent = 'Feels ' + tempMeta.fmt(data.feels_like) + tempMeta.unit;
      } else {
        weatherFeels.textContent = 'Feels ' + data.feels_like.toFixed(1) + '\u00b0';
      }
    }

    // Mark weather card as live
    const weatherCard = sensorGrid.querySelector('.weather-card');
    if (weatherCard) {
      weatherCard.classList.remove('loading');
    }
  }

  // ─── News ticker ───
  function updateHeadline() {
    if (!tickerHeadline || !tickerSection || state.headlines.length === 0) return;

    const headline = state.headlines[state.headlineIndex];
    // Fade out, swap, fade in
    tickerHeadline.classList.add('fade');
    setTimeout(() => {
      tickerSection.textContent = (headline.section || '').toUpperCase();
      tickerHeadline.textContent = headline.title || '';
      tickerHeadline.classList.remove('fade');
    }, 300);
  }

  function rotateHeadline() {
    if (state.headlines.length <= 1) return;
    state.headlineIndex = (state.headlineIndex + 1) % state.headlines.length;
    updateHeadline();
  }

  // Fetch cached news on page load (SSE only gets live updates)
  async function loadCachedNews() {
    try {
      const resp = await fetch('/api/sensors');
      if (!resp.ok) return;
      const all = await resp.json();
      const newsData = all['news.headlines'];
      if (newsData && newsData.headlines && newsData.headlines.length > 0) {
        state.headlines = newsData.headlines;
        state.headlineIndex = 0;
        updateHeadline();
      }
    } catch { /* ignore */ }
  }
  loadCachedNews();

  // Rotate headlines every 8 seconds
  setInterval(rotateHeadline, 8000);

  // Tap ticker → ask the assistant about the headline
  if (newsTicker) {
    newsTicker.addEventListener('click', () => {
      if (state.headlines.length === 0) return;
      const headline = state.headlines[state.headlineIndex];
      sendMessage(`What can you tell me about this headline: "${headline.title}"?`);
    });
  }

  // ─── Tap sensor card → ask about it (with tap feedback) ───
  sensorGrid.addEventListener('click', (e) => {
    const card = e.target.closest('.sensor-card');
    if (!card) return;

    // Visual tap feedback
    card.classList.remove('tapped');
    void card.offsetWidth; // force reflow
    card.classList.add('tapped');

    const sensor = card.dataset.sensor;
    if (sensor === 'camera') {
      showCameraOverlay();
      return;
    }
    if (sensor === 'comfort') {
      sendMessage('How is the overall comfort level? What could be improved?');
    } else if (sensor === 'weather') {
      sendMessage('Compare the indoor and outdoor conditions. Any suggestions?');
    } else {
      const meta = SENSOR_MAP[sensor];
      const value = state.sensors[sensor];
      if (value !== undefined && meta) {
        sendMessage(`Tell me about the ${sensor} reading of ${meta.fmt(value)}${meta.unit}`);
      } else {
        sendMessage(`What can you tell me about the ${sensor}?`);
      }
    }
  });

  // ─── Chat input ───
  chatInput.addEventListener('input', () => {
    sendBtn.disabled = chatInput.value.trim() === '' || state.streaming;
  });

  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !sendBtn.disabled) {
      sendMessage(chatInput.value.trim());
    }
  });

  sendBtn.addEventListener('click', () => {
    if (!sendBtn.disabled) {
      sendMessage(chatInput.value.trim());
    }
  });

  // ─── Send message & stream response ───
  async function sendMessage(text) {
    if (!text || state.streaming) return;

    // Enter immersive chat mode
    enterChatMode();
    resetChatIdleTimer();

    // Add user message
    addMessage('user', text);
    chatInput.value = '';
    sendBtn.disabled = true;

    // Build sensor context
    const context = buildSensorContext();

    // Create assistant message placeholder
    const msgEl = addMessage('assistant', '', true);
    state.streaming = true;

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          sensor_context: context,
          camera_scene: state.scene,
          history: state.messages.slice(-10),
        }),
      });

      if (!resp.ok) {
        msgEl.textContent = `Connection issue (${resp.status}). Try again.`;
        msgEl.classList.remove('streaming');
        state.streaming = false;
        sendBtn.disabled = false;
        return;
      }

      // Stream SSE response
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let fullText = '';
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete line

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const payload = line.slice(6);
            if (payload === '[DONE]') continue;
            try {
              const chunk = JSON.parse(payload);
              if (chunk.text) {
                fullText += chunk.text;
                msgEl.innerHTML = renderMarkdown(fullText);
                scrollChat();
              }
            } catch {
              // plain text chunk
              fullText += payload;
              msgEl.innerHTML = renderMarkdown(fullText);
              scrollChat();
            }
          }
        }
      }

      // Finalize
      msgEl.classList.remove('streaming');
      state.messages.push({ role: 'assistant', content: fullText });
      saveChatHistory();

    } catch (err) {
      msgEl.textContent = 'Could not reach the assistant. Check your connection.';
      msgEl.classList.remove('streaming');
    }

    state.streaming = false;
    sendBtn.disabled = chatInput.value.trim() === '';
  }

  // ─── Build structured sensor context ───
  function buildSensorContext() {
    const snapshot = {};
    Object.entries(state.sensors).forEach(([field, value]) => {
      const meta = SENSOR_MAP[field];
      if (!meta) return;
      const hist = state.history[field] || [];
      const trend = hist.length >= 3
        ? (hist[hist.length - 1] > hist[hist.length - 3] ? 'rising' : hist[hist.length - 1] < hist[hist.length - 3] ? 'falling' : 'stable')
        : 'unknown';

      snapshot[field] = {
        value: parseFloat(meta.fmt(value)),
        unit: meta.unit.trim(),
        trend: trend,
        min_recent: hist.length > 0 ? parseFloat(meta.fmt(Math.min(...hist))) : null,
        max_recent: hist.length > 0 ? parseFloat(meta.fmt(Math.max(...hist))) : null,
      };
    });

    // Weather data
    if (state.weather) {
      snapshot._weather = state.weather;
    }

    // Comfort score
    const t = state.sensors.temperature;
    const h = state.sensors.humidity;
    if (t != null && h != null) {
      snapshot._comfort = {
        score: parseInt(comfortScore.textContent) || null,
        label: comfortLabel.textContent,
      };
    }

    // System stats
    if (state.systemStats && Object.keys(state.systemStats).length > 0) {
      snapshot._system = {
        cpu_temp: state.systemStats.cpu_temp,
        ram_percent: state.systemStats.ram_percent,
        disk_percent: state.systemStats.disk_percent,
        load_1m: state.systemStats.load_1m,
        uptime: state.systemStats.uptime_str,
      };
    }

    // News headlines (last 5)
    if (state.headlines && state.headlines.length > 0) {
      snapshot._news = state.headlines.slice(0, 5).map(n => ({
        title: n.title,
        section: n.section,
      }));
    }

    // Active alerts
    if (state.activeAlerts && state.activeAlerts.length > 0) {
      snapshot._alerts = state.activeAlerts.map(a => ({
        level: a.level,
        message: a.message,
      }));
    }

    return snapshot;
  }

  // ─── DOM helpers ───
  function addMessage(role, text, streaming = false) {
    const el = document.createElement('div');
    el.className = `chat-msg ${role}${streaming ? ' streaming' : ''}`;
    if (role === 'assistant' && text) {
      el.innerHTML = renderMarkdown(text);
    } else {
      el.textContent = text;
    }
    chatMessages.appendChild(el);

    if (role === 'user') {
      state.messages.push({ role: 'user', content: text });
      saveChatHistory();
    }

    scrollChat();
    return el;
  }

  function scrollChat() {
    requestAnimationFrame(() => {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    });
  }

  // ─── Lightweight markdown → HTML ───
  function renderMarkdown(text) {
    if (!text) return '';
    let html = text
      // Escape HTML entities first
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      // Code blocks (``` ... ```)
      .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
      // Inline code (`...`)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      // Bold (**...**)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      // Italic (*...*)
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      // Headers (### ... , ## ... , # ...)
      .replace(/^### (.+)$/gm, '<strong style="font-size:0.95em">$1</strong>')
      .replace(/^## (.+)$/gm, '<strong style="font-size:1em">$1</strong>')
      .replace(/^# (.+)$/gm, '<strong style="font-size:1.1em">$1</strong>')
      // Unordered list items (- ... or * ...)
      .replace(/^[\-\*] (.+)$/gm, '<span style="display:block;padding-left:1em">\u2022 $1</span>')
      // Ordered list items (1. ...)
      .replace(/^\d+\. (.+)$/gm, '<span style="display:block;padding-left:1em">$1</span>')
      // Line breaks
      .replace(/\n/g, '<br>');
    return html;
  }

  // ─── Alert Toasts ───
  function showAlertToast(alert) {
    // Create toast container if it doesn't exist
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${alert.level || 'info'}`;
    toast.textContent = alert.message || 'Alert';

    container.appendChild(toast);

    // Auto-dismiss after 8 seconds
    setTimeout(() => {
      toast.classList.add('toast-exit');
      setTimeout(() => toast.remove(), 400);
    }, 8000);

    // Tap to dismiss
    toast.addEventListener('click', () => {
      toast.classList.add('toast-exit');
      setTimeout(() => toast.remove(), 400);
    });
  }

// ─── Chat Persistence (localStorage) ───
  function saveChatHistory() {
    try {
      const toSave = state.messages.slice(-CHAT_MAX_STORED);
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(toSave));
    } catch {
      // localStorage full or disabled
    }
  }

  function restoreChatHistory() {
    try {
      const stored = localStorage.getItem(CHAT_STORAGE_KEY);
      if (!stored) return;
      const messages = JSON.parse(stored);
      if (!Array.isArray(messages) || messages.length === 0) return;

      // Clear the default system message
      chatMessages.innerHTML = '';

      messages.forEach(msg => {
        const el = document.createElement('div');
        el.className = `chat-msg ${msg.role}`;
        if (msg.role === 'assistant') {
          el.innerHTML = renderMarkdown(msg.content);
        } else {
          el.textContent = msg.content;
        }
        chatMessages.appendChild(el);
      });

      state.messages = messages;
      scrollChat();
    } catch {
      // Corrupted storage, ignore
    }
  }

  // ─── Data freshness indicator ───
  function updateFreshness() {
    const count = Object.keys(state.sensors).length;
    if (count === 0) {
      sensorCount.textContent = 'connecting...';
      return;
    }

    const elapsed = state.lastDataTime ? Math.floor((Date.now() - state.lastDataTime) / 1000) : 0;

    if (elapsed > 60) {
      // Stale: over 1 minute
      const mins = Math.floor(elapsed / 60);
      sensorCount.textContent = `${count} sensors \u00b7 ${mins}m ago`;
      statusDot.className = 'dot warn';
    } else if (elapsed > 30) {
      // Warning: over 30 seconds
      sensorCount.textContent = `${count} active \u00b7 ${elapsed}s ago`;
      statusDot.className = 'dot warn';
    } else if (elapsed > 0) {
      sensorCount.textContent = `${count} active \u00b7 ${elapsed}s ago`;
      statusDot.className = 'dot';
    } else {
      sensorCount.textContent = `${count} active`;
      statusDot.className = 'dot';
    }
  }

  // ─── Comfort Score (0-100 from temp + humidity + VOC) ───
  const COMFORT_ARC_LEN = 79; // approximate arc path length for stroke-dasharray

  function computeComfortScore() {
    const t = state.sensors.temperature;  // Celsius
    const h = state.sensors.humidity;     // %
    const v = state.sensors.voc_index;    // 0-500

    // Need at least temp and humidity
    if (t == null || h == null) return;

    // Temperature score (0-100): ideal 20-24°C, penalty outside
    let tempScore;
    if (t >= 20 && t <= 24) {
      tempScore = 100;
    } else if (t < 20) {
      tempScore = Math.max(0, 100 - (20 - t) * 8);  // -8 per degree below 20
    } else {
      tempScore = Math.max(0, 100 - (t - 24) * 8);   // -8 per degree above 24
    }

    // Humidity score (0-100): ideal 40-60%, penalty outside
    let humidScore;
    if (h >= 40 && h <= 60) {
      humidScore = 100;
    } else if (h < 40) {
      humidScore = Math.max(0, 100 - (40 - h) * 3);
    } else {
      humidScore = Math.max(0, 100 - (h - 60) * 3);
    }

    // VOC score (0-100): <100 is excellent, >250 is poor
    let vocScore = 100;
    if (v != null) {
      if (v <= 100) {
        vocScore = 100;
      } else if (v <= 250) {
        vocScore = Math.max(0, 100 - (v - 100) * 0.67);
      } else {
        vocScore = Math.max(0, 100 - (v - 100) * 0.67);
      }
    }

    // Weighted average: temp 40%, humidity 30%, air quality 30%
    const weights = v != null ? [0.4, 0.3, 0.3] : [0.55, 0.45, 0];
    const score = Math.round(
      tempScore * weights[0] + humidScore * weights[1] + vocScore * weights[2]
    );

    // Update DOM
    comfortScore.textContent = score;

    // Arc fill: fraction of arc length
    const fill = (score / 100) * COMFORT_ARC_LEN;
    comfortArcFill.setAttribute('stroke-dasharray', `${fill.toFixed(1)} ${COMFORT_ARC_LEN}`);

    // Color the arc based on score
    let arcColor;
    if (score >= 75) {
      arcColor = 'var(--good)';
    } else if (score >= 50) {
      arcColor = 'var(--warn)';
    } else {
      arcColor = 'var(--alert)';
    }
    comfortArcFill.setAttribute('stroke', arcColor);

    // Label
    if (score >= 85) {
      comfortLabel.textContent = 'Excellent';
    } else if (score >= 70) {
      comfortLabel.textContent = 'Good';
    } else if (score >= 50) {
      comfortLabel.textContent = 'Fair';
    } else if (score >= 30) {
      comfortLabel.textContent = 'Poor';
    } else {
      comfortLabel.textContent = 'Bad';
    }
  }

  // ─── Voice input (browser MediaRecorder) ───
  let voiceState = 'idle';
  let mediaRecorder = null;
  let audioChunks = [];

  function updateVoiceState(newState) {
    voiceState = newState;
    if (!micBtn) return;
    micBtn.classList.remove('listening', 'processing', 'speaking', 'error', 'unavailable');
    if (newState !== 'idle') micBtn.classList.add(newState);
  }

  if (micBtn) {
    // Check browser support
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      micBtn.classList.add('unavailable');
      micBtn.title = 'Microphone not supported';
    }

    micBtn.addEventListener('click', async () => {
      if (micBtn.classList.contains('unavailable')) return;

      // Tap while recording → stop
      if (voiceState === 'listening') {
        if (mediaRecorder && mediaRecorder.state === 'recording') mediaRecorder.stop();
        return;
      }
      if (voiceState !== 'idle') return;

      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunks = [];

        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';

        mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});

        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) audioChunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
          stream.getTracks().forEach(t => t.stop());
          if (!audioChunks.length) { updateVoiceState('idle'); return; }

          updateVoiceState('processing');
          const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
          const formData = new FormData();
          formData.append('audio', blob, 'recording.webm');

          try {
            const resp = await fetch('/api/voice', { method: 'POST', body: formData });
            const result = await resp.json();
            if (resp.ok && result.text) {
              updateVoiceState('idle');
              sendMessage(result.text);
            } else {
              console.warn('Transcription:', result.error || 'unknown error');
              updateVoiceState('error');
              setTimeout(() => updateVoiceState('idle'), 2000);
            }
          } catch (err) {
            console.warn('Voice upload failed:', err);
            updateVoiceState('error');
            setTimeout(() => updateVoiceState('idle'), 2000);
          }
        };

        mediaRecorder.start();
        updateVoiceState('listening');

        // Auto-stop after 30s
        setTimeout(() => {
          if (mediaRecorder && mediaRecorder.state === 'recording') mediaRecorder.stop();
        }, 30000);

      } catch (err) {
        console.warn('Mic access denied:', err);
        updateVoiceState('error');
        setTimeout(() => updateVoiceState('idle'), 2000);
      }
    });
  }

  // ─── Camera overlay ───
  const cameraOverlay = document.getElementById('camera-overlay');
  const cameraFeed = document.getElementById('camera-feed');
  const cameraDescribeBtn = document.getElementById('camera-describe-btn');
  const cameraDescription = document.getElementById('camera-description');
  const cameraOverlayClose = document.getElementById('camera-overlay-close');
  let cameraPollingInterval = null;

  function showCameraOverlay() {
    if (!cameraOverlay) return;
    cameraOverlay.style.display = 'flex';
    // Start polling for live frames
    refreshCameraFrame();
    cameraPollingInterval = setInterval(refreshCameraFrame, 2000);
    // Show latest scene description if we have one
    if (state.scene) {
      cameraDescription.textContent = state.scene;
    }
  }

  function hideCameraOverlay() {
    if (cameraOverlay) cameraOverlay.style.display = 'none';
    if (cameraPollingInterval) {
      clearInterval(cameraPollingInterval);
      cameraPollingInterval = null;
    }
  }

  function refreshCameraFrame() {
    if (!cameraFeed) return;
    // Append timestamp to bust browser cache
    cameraFeed.src = '/api/camera/frame?t=' + Date.now();
  }

  // Close button
  if (cameraOverlayClose) {
    cameraOverlayClose.addEventListener('click', hideCameraOverlay);
  }

  // Click backdrop to close
  if (cameraOverlay) {
    cameraOverlay.addEventListener('click', (e) => {
      if (e.target === cameraOverlay) hideCameraOverlay();
    });
  }

  // Describe button — sends the request through chat with camera context
  if (cameraDescribeBtn) {
    cameraDescribeBtn.addEventListener('click', () => {
      cameraDescribeBtn.disabled = true;
      cameraDescription.textContent = 'Analyzing scene...';
      hideCameraOverlay();
      sendMessage('Describe what the camera sees right now in detail.');
      // Re-enable after a few seconds
      setTimeout(() => { cameraDescribeBtn.disabled = false; }, 5000);
    });
  }

  // ─── Init ───
  // Mark all sensor cards as loading until first data arrives
  sensorGrid.querySelectorAll('.sensor-card').forEach(card => {
    card.classList.add('loading');
  });

  // Restore chat history from localStorage
  restoreChatHistory();

  // Load view registry and sensor config, then connect SSE
  loadViews();
  loadConfig().then(() => {
    connectSSE();
    // Update freshness indicator every 5 seconds
    setInterval(updateFreshness, 5000);
  });

  // ─── Onscreen keyboard ───
  const osk = document.getElementById('osk');
  const oskShift = document.getElementById('osk-shift');
  let oskShiftActive = false;
  let oskNumberMode = false;
  const numberKeys = '1234567890'.split('');
  const symbolKeys = '!@#$%^&*()'.split('');
  const letterRows = [
    'qwertyuiop'.split(''),
    'asdfghjkl'.split(''),
    'zxcvbnm'.split(''),
  ];

  function showOSK() {
    if (!osk) return;
    osk.style.display = 'flex';
    body.classList.add('osk-open');
  }

  function hideOSK() {
    if (!osk) return;
    osk.style.display = 'none';
    body.classList.remove('osk-open');
  }

  function updateOSKKeys() {
    if (!osk) return;
    const keys = osk.querySelectorAll('.osk-key[data-key]');
    keys.forEach(key => {
      const k = key.dataset.key;
      if (k.length === 1 && k.match(/[a-z]/)) {
        key.textContent = oskShiftActive ? k.toUpperCase() : k;
      }
    });
  }

  // Show keyboard when input is focused, reset chat idle timer
  chatInput.addEventListener('focus', () => {
    showOSK();
    resetChatIdleTimer();
  });

  // Handle keyboard key presses
  if (osk) {
    osk.addEventListener('click', (e) => {
      const keyBtn = e.target.closest('.osk-key');
      if (!keyBtn) return;

      const key = keyBtn.dataset.key;
      e.preventDefault();
      e.stopPropagation();

      if (key === 'shift') {
        oskShiftActive = !oskShiftActive;
        if (oskShift) oskShift.classList.toggle('active', oskShiftActive);
        updateOSKKeys();
        return;
      }

      if (key === 'backspace') {
        chatInput.value = chatInput.value.slice(0, -1);
        chatInput.dispatchEvent(new Event('input'));
        return;
      }

      if (key === 'send') {
        if (chatInput.value.trim()) {
          sendMessage(chatInput.value.trim());
          hideOSK();
        }
        return;
      }

      if (key === 'numbers') {
        // Toggle number/letter mode — swap key labels
        oskNumberMode = !oskNumberMode;
        keyBtn.textContent = oskNumberMode ? 'abc' : '123';
        const rows = osk.querySelectorAll('.osk-row');
        if (rows[0]) {
          const rowKeys = rows[0].querySelectorAll('.osk-key');
          const nums = oskNumberMode ? numberKeys : letterRows[0];
          rowKeys.forEach((k, i) => {
            if (i < nums.length) {
              k.dataset.key = nums[i];
              k.textContent = nums[i];
            }
          });
        }
        return;
      }

      // Regular key
      let char = key;
      if (oskShiftActive && char.length === 1) {
        char = char.toUpperCase();
        oskShiftActive = false;
        if (oskShift) oskShift.classList.remove('active');
        updateOSKKeys();
      }

      chatInput.value += char;
      chatInput.dispatchEvent(new Event('input'));
    });

    // Close keyboard when tapping outside input area
    document.addEventListener('click', (e) => {
      if (!osk.contains(e.target) &&
          e.target !== chatInput &&
          !e.target.closest('.input-bar') &&
          !e.target.closest('.chat-mode')) {
        hideOSK();
      }
    });
  }

  // ─── Radio detail overlay ───
  const radioOverlay = document.getElementById('radio-overlay');
  const radioOverlayTitle = document.getElementById('radio-overlay-title');
  const radioOverlayBody = document.getElementById('radio-overlay-body');
  const radioOverlayClose = document.getElementById('radio-overlay-close');

  // Store latest radio data for detail display
  state.radioWifi = null;
  state.radioBle = null;

  function showRadioDetail(type) {
    if (!radioOverlay) return;

    if (type === 'wifi') {
      radioOverlayTitle.textContent = 'WiFi Networks';
      renderWifiDetail();
    } else {
      radioOverlayTitle.textContent = 'Bluetooth Devices';
      renderBleDetail();
    }

    radioOverlay.style.display = 'flex';
  }

  function hideRadioDetail() {
    if (radioOverlay) radioOverlay.style.display = 'none';
  }

  function signalPercent(dbm) {
    // Map dBm (-100 to -30) to 0-100%
    return Math.max(0, Math.min(100, ((dbm + 100) / 70) * 100));
  }

  function signalColor(dbm) {
    if (dbm >= -50) return 'var(--good)';
    if (dbm >= -70) return 'var(--warn)';
    return 'var(--alert)';
  }

  function renderWifiDetail() {
    const data = state.radioWifi;
    if (!data || !radioOverlayBody) {
      radioOverlayBody.innerHTML = '<p style="color:var(--text-dim)">No WiFi scan data yet. Waiting for next scan...</p>';
      return;
    }

    let html = '<div class="radio-summary">';
    html += `<strong>${data.network_count || 0}</strong> networks detected`;
    if (data.connected_ssid) {
      html += ` &middot; Connected to <strong>${data.connected_ssid}</strong>`;
      if (data.connected_signal) html += ` (${data.connected_signal} dBm)`;
      if (data.channel) html += ` &middot; Ch ${data.channel}`;
    }
    html += '</div>';

    // Show connected network prominently
    if (data.connected_ssid) {
      const pct = signalPercent(data.connected_signal || -70);
      html += `<div class="radio-item">
        <div>
          <div class="radio-item-name">${data.connected_ssid}</div>
          <span class="radio-connected">connected</span>
        </div>
        <div class="radio-item-meta">
          <span class="radio-signal">${data.connected_signal || '--'} dBm</span>
          <span class="radio-signal-bar"><span class="radio-signal-fill" style="width:${pct}%;background:${signalColor(data.connected_signal || -70)}"></span></span>
        </div>
      </div>`;
    }

    // Show strongest if different from connected
    if (data.strongest_ssid && data.strongest_ssid !== data.connected_ssid) {
      const pct = signalPercent(data.strongest_signal || -70);
      html += `<div class="radio-item">
        <div class="radio-item-name">${data.strongest_ssid}</div>
        <div class="radio-item-meta">
          <span class="radio-signal">${data.strongest_signal || '--'} dBm</span>
          <span class="radio-signal-bar"><span class="radio-signal-fill" style="width:${pct}%;background:${signalColor(data.strongest_signal || -70)}"></span></span>
          <span style="color:var(--text-dim)">strongest</span>
        </div>
      </div>`;
    }

    radioOverlayBody.innerHTML = html;
  }

  function renderBleDetail() {
    const data = state.radioBle;
    if (!data || !radioOverlayBody) {
      radioOverlayBody.innerHTML = '<p style="color:var(--text-dim)">No Bluetooth scan data yet. Waiting for next scan...</p>';
      return;
    }

    const total = data.total_count || data.ble_device_count || 0;
    const classic = data.classic_count || 0;
    const ble = data.ble_device_count || total;
    const names = data.device_names || [];

    let html = '<div class="radio-summary">';
    html += `<strong>${total}</strong> devices detected`;
    if (ble > 0 && classic > 0) {
      html += ` (${ble} BLE, ${classic} classic)`;
    }
    html += '</div>';

    if (names.length > 0) {
      names.forEach(name => {
        html += `<div class="radio-item">
          <div class="radio-item-name">${name}</div>
          <div class="radio-item-meta"><span style="color:var(--cyan-dim)">BLE</span></div>
        </div>`;
      });
    } else {
      html += '<p style="color:var(--text-dim);padding:8px 0">No named devices found. Unnamed devices: ' + total + '</p>';
    }

    radioOverlayBody.innerHTML = html;
  }

  // ─── All Sensors overlay ───
  const sensorOverlay = document.getElementById('sensor-overlay');
  const sensorOverlayBody = document.getElementById('sensor-overlay-body');
  const sensorOverlayClose = document.getElementById('sensor-overlay-close');

  // (SENSOR_LABELS defined near top of file)

  function showAllSensors() {
    if (!sensorOverlay || !sensorOverlayBody) return;

    let html = '';
    const fields = Object.keys(SENSOR_MAP);

    if (fields.length === 0) {
      html = '<p style="color:var(--text-dim);grid-column:1/-1">No sensor data available yet.</p>';
    } else {
      fields.forEach(field => {
        const meta = SENSOR_MAP[field];
        const value = state.sensors[field];
        const hist = state.history[field] || [];
        let trendHtml = '';

        if (hist.length >= 3) {
          const recent = hist.slice(-3);
          const avg = recent.reduce((a, b) => a + b, 0) / recent.length;
          const older = hist.slice(0, Math.max(1, hist.length - 3));
          const oldAvg = older.reduce((a, b) => a + b, 0) / older.length;
          const diff = avg - oldAvg;
          const pct = oldAvg !== 0 ? Math.abs(diff / oldAvg) * 100 : 0;

          if (pct > 2) {
            const dir = diff > 0 ? 'up' : 'down';
            trendHtml = `<span class="sensor-trend trend-${dir}">${dir === 'up' ? '&#9650;' : '&#9660;'} ${dir === 'up' ? 'rising' : 'falling'}</span>`;
          } else {
            trendHtml = '<span class="sensor-trend trend-stable">&#9679; stable</span>';
          }
        } else {
          trendHtml = '<span class="sensor-trend trend-stable">&#9679; waiting</span>';
        }

        const label = SENSOR_LABELS[field] || field;
        const formatted = value != null ? meta.fmt(value) : '--';

        html += `<div class="all-sensor-item" data-field="${field}">
          <span class="sensor-label">${label}</span>
          <span class="sensor-value">${formatted}<span class="sensor-unit">${meta.unit}</span></span>
          ${trendHtml}
        </div>`;
      });
    }

    sensorOverlayBody.innerHTML = html;
    sensorOverlay.style.display = 'flex';

    // Tap a sensor in the overlay to ask about it
    sensorOverlayBody.querySelectorAll('.all-sensor-item').forEach(item => {
      item.addEventListener('click', () => {
        const field = item.dataset.field;
        const meta = SENSOR_MAP[field];
        const value = state.sensors[field];
        hideAllSensors();
        if (value != null && meta) {
          sendMessage(`Tell me about the ${SENSOR_LABELS[field] || field} reading of ${meta.fmt(value)}${meta.unit}`);
        } else {
          sendMessage(`What can you tell me about the ${SENSOR_LABELS[field] || field}?`);
        }
      });
    });
  }

  function hideAllSensors() {
    if (sensorOverlay) sensorOverlay.style.display = 'none';
  }

  if (sensorOverlayClose) {
    sensorOverlayClose.addEventListener('click', hideAllSensors);
  }
  if (sensorOverlay) {
    sensorOverlay.addEventListener('click', (e) => {
      if (e.target === sensorOverlay) hideAllSensors();
    });
  }

  // Badge click handlers
  if (wifiBadge) {
    wifiBadge.addEventListener('click', () => showRadioDetail('wifi'));
  }
  if (bleBadge) {
    bleBadge.addEventListener('click', () => showRadioDetail('ble'));
  }
  if (radioOverlayClose) {
    radioOverlayClose.addEventListener('click', hideRadioDetail);
  }
  if (radioOverlay) {
    radioOverlay.addEventListener('click', (e) => {
      if (e.target === radioOverlay) hideRadioDetail();
    });
  }

})();
