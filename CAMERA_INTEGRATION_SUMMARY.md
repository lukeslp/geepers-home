# Camera Integration Summary

**Hardware**: Raspberry Pi 3B+ (1.4GHz quad-core, 1GB RAM)
**Camera**: Logitech Brio 100 (USB webcam, MJPEG support)
**Analysis Date**: 2026-02-12

---

## TL;DR

**YES, the Pi 3B+ can handle camera integration, BUT:**
- **MUST add heatsink** (or 5V fan) to prevent throttling
- Start with **Phase 1** (160x120 preview, 5-minute snapshots)
- Monitor temps for 24 hours before adding more features
- Expect **55-70% CPU usage** (up from current 15-20%)
- RAM usage is safe: **180-200MB** of 1GB

---

## Recommended Implementation: Phase 1

### Hardware Requirements
- **Heatsink** (passive cooling) — $3-5, prevents throttling
- OR **5V fan** — $5-10, enables Phase 2 features

### Software Changes
1. **Camera preview**: 160x120 @ 5fps MJPEG
   - Use v4l2-python or OpenCV VideoCapture
   - Resize to 250x180 for tkinter display
   - **CPU impact**: +15%

2. **Snapshots**: 720p JPEG every 5 minutes
   - Write to `/tmp/snapshots/` (tmpfs, zero SD wear)
   - Batch-upload 5-10 snapshots to VPS
   - **CPU impact**: +2% sustained, +15% burst for 1-2s

3. **LLM vision analysis**: HTTP POST snapshot to VPS
   - Background thread with 5s timeout
   - Display response text in new card
   - **Network impact**: 3.3KB/s (negligible)

4. **Skip motion detection** initially
   - Saves 5-8% CPU for Phase 1
   - Add in Phase 2 if thermal budget allows

### Projected Resources (Phase 1)
| Metric | Current | Phase 1 | Safe? |
|--------|---------|---------|-------|
| CPU | 15-20% | 45-55% | ✅ Yes (30-45% headroom) |
| RAM | 45MB | 180MB | ✅ Yes (820MB free) |
| Thermal | 50-55°C | 62-68°C | ✅ Yes with heatsink |
| SD Write | ~1KB/s | 0 | ✅ Yes (tmpfs) |

---

## Phase 2 (Requires 5V Fan)

After 24-hour thermal stability test with Phase 1:

1. **Add motion detection** (background thread)
   - numpy frame differencing every 2s
   - **CPU impact**: +5-8%

2. **Upgrade preview to 320x240** (optional)
   - Only if temps stay <65°C with 160x120
   - **CPU impact**: +10% over Phase 1

### Projected Resources (Phase 2)
| Metric | Phase 1 | Phase 2 | Safe? |
|--------|---------|---------|-------|
| CPU | 45-55% | 65-75% | ✅ Yes with fan |
| RAM | 180MB | 200-250MB | ✅ Yes (750MB free) |
| Thermal | 62-68°C | 55-60°C | ✅ Yes with fan |

---

## Bottlenecks & Risks

### 1. Thermal Throttling (HIGH RISK)
- **Pi 3B+ throttles at 80°C**: CPU drops from 1.4GHz to 600MHz
- **Projected temp without cooling**: 75-82°C (WILL THROTTLE)
- **Projected temp with heatsink**: 62-68°C (SAFE)
- **Projected temp with fan**: 55-60°C (VERY SAFE)
- **Time to throttle**: 10-20 minutes of continuous camera operation

**Mitigation**: Add heatsink (minimum) or 5V fan (recommended)

---

### 2. Camera Frame Drops (MEDIUM RISK)
- **5fps is the limit**: Any CPU spike >200ms drops frames
- **USB bus is shared**: Other USB devices can cause interference
- **MJPEG is fragile**: Dropped frames cause visible stuttering

**Mitigation**:
- Use dedicated USB port for camera (no hub)
- Reduce preview to 160x120 if drops detected
- Implement frame skip logic: "show latest available, don't wait"

---

### 3. Main Thread Blocking (MEDIUM RISK)
- **tkinter is single-threaded**: All UI updates on main thread
- **Frame conversion (8ms)** + **motion detection (5ms)** = **13ms blocked**
- **EventBus processes 50 msg/tick**: Camera adds 10 events/sec

**Mitigation**:
- Move motion detection to background thread
- PIL conversion in background, only PhotoImage on main thread
- Increase EventBus capacity to 100 msg/tick

---

### 4. SD Card Wear (LOW RISK, HIGH IMPACT)
- **Direct 720p writes**: 50KB/s = 4.3GB/day = 1.5TB/year
- **Write amplification**: 10x for small writes
- **SD card lifespan**: ~3000 write cycles = 3-5 years at this rate

**Mitigation**:
- Write to `/tmp/` (tmpfs in RAM, zero SD writes)
- Batch-upload every 5-10 snapshots
- Rotate old snapshots (keep last 100)

---

## Alternative: Burst Mode (If No Cooling)

If continuous camera operation causes problems:

**Implementation**:
- Camera OFF by default
- User taps "Camera" button → turns on for 60 seconds
- Captures 5fps preview + 3 snapshots + motion detect
- Auto-shutoff after 60s or manual "Stop" button

**Benefits**:
- Eliminates thermal buildup
- Saves ~30% CPU when camera off
- Preserves USB bandwidth

---

## Test Plan

Before full deployment:

1. **Thermal baseline**: Current dashboard for 30min, log temps every 10s
2. **Camera only**: Add preview, monitor 30min
3. **Camera + snapshots**: Add 720p every 5min, watch for throttling
4. **Full workload**: All features, monitor 1 hour
5. **Stress test**: Run 6+ hours to verify stability

**Monitoring commands**:
```bash
# CPU temperature (should stay <75°C)
watch -n 1 cat /sys/class/thermal/thermal_zone0/temp

# Check throttling (0x0 = none, 0x50005 = throttled)
vcgencmd get_throttled

# CPU frequency (should stay 1400000, drops to 600000 if throttled)
watch -n 1 cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
```

---

## Cost & Time Estimate

**Hardware**:
- Heatsink: $3-5 (passive, good enough for Phase 1)
- 5V fan: $5-10 (active, enables Phase 2)
- Total: **$5-10**

**Implementation Time**:
- Phase 1 core: 4-6 hours
- UI integration: 2-3 hours
- Testing & tuning: 3-5 hours
- Total: **2-3 days** (with testing)

---

## Decision Matrix

| Cooling | Features | CPU | Thermal | Reliable? | Cost |
|---------|----------|-----|---------|-----------|------|
| None | Preview only (30s bursts) | 45% | 75°C | ⚠️ Marginal | $0 |
| Heatsink | Phase 1 (160x120 + snapshots) | 55% | 65°C | ✅ Yes | $3-5 |
| Fan | Phase 2 (320x240 + motion) | 70% | 58°C | ✅ Yes | $5-10 |

**Recommendation**: **Heatsink minimum**, **fan preferred** for long-term reliability.

---

## Next Steps

1. ✅ Performance analysis complete (this document)
2. ⬜ Order heatsink/fan ($5-10)
3. ⬜ Implement Phase 1 camera integration
4. ⬜ Run 24-hour thermal stability test
5. ⬜ Add motion detection (Phase 2) if temps stable <65°C
6. ⬜ Add to session checkpoint workflows

---

**Full report**: `/home/coolhand/geepers/reports/by-date/2026-02-12/perf-sensor-playground-camera.md`
**Recommendations**: `/home/coolhand/geepers/recommendations/by-project/sensor-playground-mirror.md`
