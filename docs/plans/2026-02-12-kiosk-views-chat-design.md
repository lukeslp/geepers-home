# Geepers Kiosk: Multi-View + Immersive Chat Design

**Date**: 2026-02-12
**Target**: 800x480 7" Raspberry Pi touchscreen kiosk
**Status**: Approved (brainstorming complete)

---

## 1. Architecture Overview

Transform the Geepers sensor dashboard from a single-purpose sensor display into a multi-view kiosk platform with an immersive conversational chat mode.

**Layout**: Header (28px) + Content Area (408px) + Input Bar (44px compact / 84px with chips)

```
┌──────────────────────────────────────────────────────┐
│ Geepers  [Sensors][Earth][Quakes][Zen]  ● 12  14:32 │ 28px
├──────────────────────────────────────────────────────┤
│                                                      │
│            Active View (full-width default)           │
│                    780 × 408                         │ 408px
│                                                      │
│         OR split mode: 388 │24│ 388                  │
│                                                      │
├──────────────────────────────────────────────────────┤
│ 🎤  Ask about your environment...            [▶]    │ 44px
└──────────────────────────────────────────────────────┘
```

**Three modes**:
- **Full-width** (default): Single view gets 780x408
- **Split** (optional): Two side-by-side panels, 388x408 each, 24px divider
- **Chat** (on engagement): Dashboard morphs into conversational layout

---

## 2. View Registry

Each view is defined in config and rendered either natively or via iframe.

### View Definitions

| ID | Label | Type | Source URL | Split OK? | Notes |
|----|-------|------|-----------|-----------|-------|
| `sensors` | Sensors | native | -- | YES | 2-col grid in split, 4-col full |
| `camera` | Camera | native | -- | YES | Single img + describe btn |
| `news` | News | native | -- | YES | Text-based, flows naturally |
| `earth` | Earth | iframe | `/datavis/dashboards/live-earth/` | YES | Globe + ticker, ambient |
| `earthquakes` | Quakes | iframe | `/datavis/dashboards/earthquakes/` | YES | D3 map, scales perfectly |
| `keep-looking` | UFOs | iframe | `/datavis/poems/keep-looking/` | YES | D3 fullscreen, minimal UI |
| `whispers` | Haunted | iframe | `/datavis/poems/whispers/` | YES | D3 spiral, minimal UI |
| `keep-up` | Rent | iframe | `/datavis/poems/keep-up/` | YES | D3 bump chart |
| `weather` | Weather | iframe | Windy/Open-Meteo embed | PARTIAL | Needs 600px+ for detail |
| `symphony` | Ambient | iframe | `/datavis/dashboards/symphony/` | PARTIAL | Controls stack oddly <500px |
| `coinfall` | Crypto | iframe | `/datavis/dashboards/coinfall/` | PARTIAL | Info panel breaks <500px |
| `attractive` | Attractors | iframe | `/datavis/attractive/` | NO | Sidebar essential, 768px min |
| `admin` | Admin | iframe | `/admin/` | NO | Grid needs scrolling |

### Split-Compatible Subset (8 views)

These work well at 388px wide:
1. **Sensors** (native) — 2-column card grid
2. **Camera** (native) — single image frame
3. **News** (native) — headline text
4. **Earth** (iframe) — globe auto-scales
5. **Earthquakes** (iframe) — D3 map auto-scales
6. **Keep Looking** (iframe) — fullscreen D3
7. **Whispers** (iframe) — fullscreen D3
8. **Keep Up** (iframe) — fullscreen D3

### Partial Split (3 views — work with CSS overrides)

These could work at 388px with targeted tweaks:
- **Weather**: Hide detail sidebar, show map only
- **Symphony**: Stack controls vertically
- **Coinfall**: Hide info panel

### Full-Width Only (2 views)

Must be shown full-width (780px):
- **Attractive** — sidebar controls essential
- **Admin** — scrollable grid directory

---

## 3. View Switching UX

### Header Tabs

View selector lives in the header as horizontally-scrollable chips:

```html
<div class="view-tabs" id="view-tabs">
  <button class="view-tab active" data-view="sensors">Sensors</button>
  <button class="view-tab" data-view="earth">Earth</button>
  <button class="view-tab" data-view="earthquakes">Quakes</button>
  ...
</div>
```

- Active tab gets neumorphic inset shadow (`--neo-in-sm`)
- Inactive tabs get raised shadow (`--neo-out-sm`)
- Tabs scroll horizontally if more than ~5 fit
- Sensor count badge + clock stay fixed right in header

### Swipe Navigation

Horizontal swipe on content area switches to adjacent view (left/right in tab order). Disabled when viewing scrollable/interactive iframes (detect iframe focus).

### Split Mode Toggle

A small split icon in header (between tabs and status area) toggles split mode:
- **Single tap**: Enter split mode (current view goes left, next in list goes right)
- **In split mode**: Each panel gets a mini-header (24px) with dropdown view selector + maximize button
- **Maximize**: Tap expand icon on either panel to go back to full-width with that view

### Split Mode Mini-Headers

```
┌─────────────────────┬──┬─────────────────────┐
│ [Sensors ▾]    [⛶] │  │ [Earth ▾]      [⛶] │ 24px mini-headers
├─────────────────────┤  ├─────────────────────┤
│                     │  │                     │
│  Left panel         │  │  Right panel        │
│  384 × 384          │  │  384 × 384          │
│                     │  │                     │
└─────────────────────┴──┴─────────────────────┘
                      24px divider
```

**Divider interaction** (preset ratios, not drag):
- Single tap: Cycle 50/50 → 65/35 → 35/65 → 50/50
- Double tap: Maximize left panel
- Only appears in split mode

### View Selector Dropdown

In split mode, each panel's dropdown only shows split-compatible views (8 + 3 partial). Full-width-only views (Attractive, Admin) are grayed out with "Full only" label.

---

## 4. Immersive Chat Mode

When the user engages with chat (types, taps mic, or taps a sensor card), the dashboard morphs into a conversational layout.

### Trigger

- User taps input field, mic button, or a sensor card
- 400ms CSS transition (smooth morph)

### Layout Transform

**Before (Dashboard Mode)**:
```
┌──────────────────────────────────────┐
│ Header + view tabs                   │
├──────────────────────────────────────┤
│ Active view (full content area)      │
├──────────────────────────────────────┤
│ Input bar                            │
└──────────────────────────────────────┘
```

**After (Chat Mode)**:
```
┌──────────────────────────────────────┐
│ Header (tabs hidden, "← Back" shown) │
├──────────┬───────────────────────────┤
│ Context  │                           │
│ strip    │   Chat messages area      │
│ (mini    │   with live mini-cards    │
│ sensors) │   inline in responses     │
│ 120px    │        660px              │
├──────────┴───────────────────────────┤
│ 🎤  [suggestion chips...]           │
│     [input field              ] [▶] │
└──────────────────────────────────────┘
```

### Context Strip (120px left column)

Compact vertical strip showing key sensor readings as small neumorphic chips. The sensor that was tapped (if any) appears first and enlarged. Data stays live.

```html
<div class="context-strip">
  <div class="context-chip active">
    <span class="chip-label">Temp</span>
    <span class="chip-value">23.4°</span>
  </div>
  <div class="context-chip">
    <span class="chip-label">Humid</span>
    <span class="chip-value">45%</span>
  </div>
  <!-- more chips... -->
</div>
```

### Live Mini-Cards in Messages

When the assistant references sensor data, inline live-updating cards appear in the message:

```html
<div class="chat-msg assistant">
  <p>The temperature is comfortable right now.</p>
  <div class="inline-sensor" data-sensor="temperature">
    <span class="inline-value">23.4°C</span>
    <span class="inline-trend up">+0.2/hr</span>
  </div>
  <p>Humidity is in the ideal range too.</p>
</div>
```

These mini-cards continue updating via SSE even after the message is rendered.

### Exit Chat Mode

- **Swipe right** on chat area → morphs back to dashboard
- **Tap "← Back"** in header → morphs back
- **45s idle timeout** → auto-morph back (no interaction = return to ambient dashboard)
- Chat history persists in localStorage (`geepers_chat` key, already implemented)

---

## 5. Input Bar Design

### Compact Mode (44px — dashboard view)

```html
<div class="input-bar compact">
  <button class="mic-btn" id="mic-btn">🎤</button>
  <input class="chat-input" placeholder="Ask about your environment...">
  <button class="send-btn" id="send-btn">▶</button>
</div>
```

### Expanded Mode (84px — chat view)

When chat mode activates, the input bar grows to show suggestion chips:

```html
<div class="input-bar expanded">
  <div class="suggestion-chips">
    <button class="chip">What's the air quality?</button>
    <button class="chip">Show weather forecast</button>
    <button class="chip">Describe the camera</button>
  </div>
  <div class="input-row">
    <button class="mic-btn">🎤</button>
    <input class="chat-input" placeholder="Ask about your environment...">
    <button class="send-btn">▶</button>
  </div>
</div>
```

### Suggestion Chips

Horizontally scrollable, context-aware:
- Default: General environment questions
- After sensor tap: Questions about that sensor ("Is 45% humidity normal?", "Show trend")
- After weather view: Weather-specific ("Will it rain?", "UV forecast")
- Neumorphic pill style with `--neo-out-sm`, tap triggers `--neo-in-sm`

### Voice-First Strategy

Mic button is prominent (leftmost). On the 7" touch screen, voice is the primary input method. The text input and on-screen keyboard are fallback only — the OSK appears only when the user explicitly taps the text field, and it uses a compact 3-row layout to minimize vertical coverage.

---

## 6. Iframe Management

### Lazy Loading

Iframes load only when their view is first activated:

```javascript
function activateView(viewId) {
  const view = VIEWS[viewId];
  if (view.type === 'iframe' && !view.loaded) {
    const iframe = document.getElementById(`view-${viewId}`);
    iframe.src = view.src;
    view.loaded = true;
  }
}
```

### State Preservation

When switching views, iframes get `display: none` (not removed). This preserves:
- 3D scene state (Three.js in Symphony, Attractive)
- Map position/zoom (Live Earth, Earthquakes)
- Audio playback (Symphony ambient loops)
- Scroll position (Admin)

### Performance

- Max 3 iframes loaded simultaneously (LRU eviction for Pi memory)
- Native views (sensors, camera, news) have zero iframe overhead
- Monitor Pi memory via existing SystemSource; auto-evict if RAM < 200MB

### Cross-Origin

All embeddable views are on the same domain (dr.eamer.dev), served via Caddy. No CORS issues. External embeds (Windy weather maps) may need `allow` attributes on the iframe.

---

## 7. Configuration

### views.yaml (new file, or add to dashboard.yaml)

```yaml
views:
  - id: sensors
    label: Sensors
    type: native
    default: true
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

---

## 8. Design Tokens (Additions)

New CSS custom properties for the kiosk features:

```css
:root {
  /* Panel system */
  --panel-header-h: 24px;
  --divider-w: 24px;
  --panel-radius: calc(var(--radius) - 4px);

  /* Chat mode */
  --context-strip-w: 120px;
  --chat-transition: 400ms var(--ease);

  /* Suggestion chips */
  --chip-h: 28px;
  --chip-font: 12px;

  /* Input bar heights */
  --input-compact-h: 44px;
  --input-expanded-h: 84px;

  /* Depth layers (nested neumorphism) */
  --neo-container: inset 1px 1px 3px var(--shadow-dark),
                   inset -1px -1px 3px var(--shadow-light);
}
```

---

## 9. State Machine

```
                    ┌──────────────┐
          ┌─────── │  FULL-WIDTH   │ ◄──────┐
          │        │  (default)    │        │
          │        └──────┬───────┘        │
          │               │                │
     split-toggle    chat-engage      maximize
          │               │                │
          ▼               ▼                │
   ┌──────────────┐  ┌──────────────┐      │
   │  SPLIT-VIEW  │  │  CHAT-MODE   │      │
   │  (optional)  │  │  (immersive) │      │
   └──────┬───────┘  └──────┬───────┘      │
          │               │                │
     chat-engage     back/idle/swipe       │
          │               │                │
          ▼               ▼                │
   ┌──────────────┐  ┌──────────────┐      │
   │ SPLIT+CHAT   │  │  FULL-WIDTH  │ ─────┘
   │ (both active) │  │  (restored)  │
   └──────────────┘  └──────────────┘
```

Views persist across mode changes. Chat mode overlays on top of the current view configuration.

---

## 10. Implementation Priority

1. **P0 — View switcher**: Header tabs + full-width iframe loading (core feature)
2. **P0 — View registry**: Config-driven view definitions with lazy loading
3. **P1 — Immersive chat**: Conversational mode swap with context strip
4. **P1 — Suggestion chips**: Context-aware input helpers
5. **P2 — Split mode**: Optional dual-panel with mini-headers and divider
6. **P2 — Swipe navigation**: Gesture-based view switching
7. **P3 — LRU iframe eviction**: Memory management for Pi
8. **P3 — Dense sensor mode**: Compact card layout for split panels
