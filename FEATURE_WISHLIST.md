# Feature Wishlist

Repos and projects with specific functional applications to integrate into the sensor dashboard.

---

## 1. pi-sniffer — BLE People Counter

**Repo:** https://github.com/IanMercer/pi-sniffer
**Status:** Not started

BLE scanning system that counts nearby people by detecting mobile devices. Written in C with minimal dependencies (just Eclipse PAHO MQTT). Detects BLE devices, reports MAC addresses, names, types, UUIDs, and approximate distances using Kalman filtering. Handles iPhone MAC randomization to estimate true device counts.

**Why it's useful:**
- Presence detection — know who's home based on phone proximity
- Room occupancy counting for automation triggers
- Distance estimation via signal strength + Kalman smoothing
- MQTT output integrates cleanly with our event bus

**Integration approach:**
- Build as a new DataSource that subscribes to MQTT topics from pi-sniffer
- Or wrap the C binary as a subprocess (like the WiFi/BLE scanners already do)
- Feed device count + nearest device distance into the dashboard
- Could replace or supplement the existing `BluetoothScannerSource` with richer data

**Hardware needed:**
- Already have Pi 3B+ with built-in Bluetooth
- May need MQTT broker (mosquitto) running locally

**Depends on:** MQTT broker setup

---

## 2. FindMy.py — Apple FindMy Network Tracker

**Repo:** https://github.com/malmeloo/FindMy.py
**Status:** Not started

Python library for querying Apple's FindMy network — locate AirTags, iDevices, and custom OpenHaystack tags without a Mac. Supports SMS and Trusted Device 2FA, async/sync APIs, and custom accessory key import.

**Why it's useful:**
- Track AirTags and Apple devices from the Pi dashboard
- Locate personal items (keys, bags, bikes) on a map or as distance indicators
- Custom tag support — could build OpenHaystack trackers with ESP32s
- Pure Python, installable via pip

**Integration approach:**
- New DataSource polling FindMy locations at intervals
- Display tracked items as a card or overlay with last-seen time and location
- Could tie into presence detection (are my keys at home?)

**Hardware needed:**
- Apple account with 2FA
- Optional: custom OpenHaystack tags (ESP32-based)

**Depends on:** Apple account credentials, network access

---

## 3. bluing — Bluetooth Intelligence Gathering

**Repo:** https://github.com/fO-000/bluing
**Status:** Not started

Python tool for deep Bluetooth protocol analysis. Scans BR/EDR and BLE devices, enumerates GATT profiles, extracts SDP databases, analyzes pairing features, and supports device spoofing. Plugin system for extensibility.

**Why it's useful:**
- Much deeper device fingerprinting than basic BLE scans
- GATT profile enumeration reveals device capabilities
- LMP feature detection identifies device types accurately
- Could feed richer device metadata into the dashboard

**Integration approach:**
- Use as a library for enhanced device scanning in `BluetoothScannerSource`
- Run periodic deep scans and cache results (these are slower than basic scans)
- Display device type, manufacturer, and capabilities in the BLE overlay

**Hardware needed:**
- Built-in Bluetooth adapter (already have)
- Optional: Ubertooth One for BR/EDR sniffing, micro:bit for LE channel sniffing

**Depends on:** Python bluez bindings

---

## 4. ESP32-Sour-Apple — BLE Spam Detection (Defensive)

**Repo:** https://github.com/RapierXbox/ESP32-Sour-Apple
**Status:** Not started

BLE exploit that spams pairing requests to iOS devices. Has Raspberry Pi implementation. Useful as a reference for **detecting** this type of attack — build a defensive scanner that alerts when BLE spam is happening nearby.

**Why it's useful:**
- Understand BLE spam attack patterns to build detection
- Alert when unusual BLE pairing request floods are detected
- Defensive awareness — know if someone is running this near your devices
- Has a Pi-native implementation to study

**Integration approach:**
- Study the attack pattern, then build a detection heuristic in our BLE scanner
- Alert card: "BLE spam detected — X pairing requests in Y seconds"
- Purely defensive — detect and alert, not replicate

**Hardware needed:**
- Built-in Bluetooth (already have)

**Depends on:** Enhanced BLE scanning (see #3 bluing)

---

## 5. Bluestrike — Bluetooth Signal Analysis

**Repo:** https://github.com/StealthIQ/Bluestrike
**Status:** Not started

Python CLI tool for Bluetooth signal analysis and security research. MAC address generation with IEEE OUI specs, traffic analysis, and device discovery. Still in development.

**Why it's useful:**
- OUI-based manufacturer identification for nearby devices
- Signal analysis patterns applicable to our scanner
- MAC address intelligence for device fingerprinting

**Integration approach:**
- Borrow OUI lookup logic for identifying device manufacturers in our BLE overlay
- Show manufacturer names alongside detected devices (e.g., "Apple iPhone", "Samsung Galaxy")

**Hardware needed:**
- Built-in Bluetooth (already have)

**Depends on:** bluez/bluez-utils

---

## 6. bluetooth-proximity — RSSI Distance Detection

**Repo:** https://github.com/ewenchou/bluetooth-proximity
**Status:** Not started

Python utilities for detecting Bluetooth device proximity using RSSI measurements. Calculates distance using Log-Normal Shadowing Model. Threaded scanning with callback support for proximity threshold events.

**Why it's useful:**
- Distance estimation from RSSI — know how far devices are
- Proximity callbacks — trigger automations when devices enter/leave range
- Log-Normal Shadowing Model is more accurate than raw RSSI
- Lightweight, pure Python

**Integration approach:**
- Integrate proximity detection into `BluetoothScannerSource`
- Track known devices (family phones) and show distance on dashboard
- Trigger alerts/automations on proximity thresholds (e.g., "phone left home")
- Complements pi-sniffer's Kalman filtering approach

**Hardware needed:**
- Built-in Bluetooth (already have)

**Depends on:** python-bluez

---

## 7. bluetooth-hacking — Bluetooth Security Toolkit

**Repo:** https://github.com/zedxpace/bluetooth-hacking-
**Status:** Not started

Educational Python scripts covering Bluetooth discovery, SDP browsing, OBEX, RCOMM scanning, sniffing, and vulnerability testing. GPL-3.0 licensed.

**Why it's useful:**
- Reference implementations for various Bluetooth scanning techniques
- SDP browsing reveals services running on nearby devices
- OBEX and RCOMM patterns useful for understanding device capabilities
- Good learning resource for extending our scanner

**Integration approach:**
- Cherry-pick scanning and discovery techniques for richer device enumeration
- SDP service browsing could show what services nearby devices expose
- Reference only — extract patterns, don't run exploits

**Hardware needed:**
- Built-in Bluetooth (already have)

**Depends on:** bluez, Python bluetooth libraries

---

## 8. blueborne-scanner — Vulnerability Detection

**Repo:** https://github.com/hook-s3c/blueborne-scanner
**Status:** Not started

Python scanner that identifies Bluetooth devices vulnerable to BlueBorne exploits (CVE-2017-0781 through 0785). Scans nearby devices and cross-references MACs against known vulnerable manufacturer OUIs.

**Why it's useful:**
- Security awareness — know if devices on your network have unpatched Bluetooth
- OUI-based vulnerability mapping is a useful pattern
- Lightweight, minimal dependencies
- Could alert: "3 devices nearby with known Bluetooth vulnerabilities"

**Integration approach:**
- Run as periodic scan alongside regular BLE scanning
- Display vulnerability status in the BLE device overlay
- Alert card when vulnerable devices detected nearby
- Good complement to bluing (#3) for security posture monitoring

**Hardware needed:**
- Built-in Bluetooth (already have)

**Depends on:** Python bluetooth libraries

---

## 9. sherpa-onnx — Offline Speech Processing Toolkit

**Repo:** https://github.com/k2-fsa/sherpa-onnx
**Status:** Not started

Comprehensive offline speech processing via ONNX runtime. Supports STT (streaming and non-streaming), TTS, speaker diarization, VAD, keyword spotting, and audio tagging. Runs on Raspberry Pi (ARM 32/64-bit), Android, iOS, and embedded Linux. Pre-trained models include Zipformer, Paraformer, and Whisper variants.

**Why it's useful:**
- Most actively maintained offline STT option for Pi
- Streaming mode enables real-time transcription as user speaks
- VAD (voice activity detection) handles silence detection automatically
- TTS support means voice output when speakers are ready
- Keyword spotting could be used for wake word detection
- Multiple model architectures to balance speed vs accuracy
- Python, C++, and JS bindings available

**Integration approach:**
- Primary candidate for on-Pi STT engine
- Use streaming mode for real-time feedback during recording
- VAD handles auto-stop when user finishes speaking
- Keyword spotting for optional wake word ("Hey Geepers")
- Later: TTS for voice responses

**Hardware needed:**
- Already have Pi 3B+ (ARM supported)

**Depends on:** ONNX Runtime (pip installable)

---

## 10. vosk-api — Offline Speech Recognition

**Repo:** https://github.com/alphacep/vosk-api
**Status:** Not started

Offline speech recognition supporting 20+ languages. Small models (~50MB) designed for resource-constrained devices including Raspberry Pi. Zero-latency streaming API. Bindings for Python, Java, Node.js, C#, C++, Rust, Go. Apache 2.0 licensed. 14.2k stars.

**Why it's useful:**
- Specifically designed for Pi-class hardware (~300MB runtime memory)
- Small English model is ~40-50MB
- Streaming API with real-time partial results
- Speaker identification built in
- Well-established community (14k+ stars)
- Reconfigurable vocabulary

**Integration approach:**
- Alternative to sherpa-onnx for on-Pi STT
- Could run as fallback when VPS is unreachable
- Streaming partial results enable live transcription display
- Lower accuracy than Whisper but much lighter on resources

**Hardware needed:**
- Already have Pi 3B+ with built-in mic via Brio 100

**Depends on:** vosk Python package, model download

---

## 11. DeepSpeech — Mozilla's STT Engine (Archived)

**Repo:** https://github.com/mozilla/DeepSpeech
**Status:** Not started (archived June 2025 — reference only)

Mozilla's open-source offline STT engine based on Baidu's Deep Speech research. Was designed to run on devices from Pi to GPU servers. 26.7k stars. No longer maintained — archived and read-only. Last release v0.9.3 (December 2020).

**Why it's useful:**
- Reference architecture for embedded STT
- Large community of forks and derivatives still active
- TensorFlow-based, well-documented model format
- Historical reference for how offline STT should work

**Integration approach:**
- Reference only — don't build on archived code
- Study the architecture for ideas applicable to sherpa-onnx or Vosk
- Community forks may have more recent improvements

**Hardware needed:**
- N/A (reference only)

**Depends on:** N/A (archived)

---

## 12. Bjorn — Autonomous Network Security Scanner

**Repo:** https://github.com/infinition/Bjorn
**Status:** Not started

Python-based autonomous network security platform with a Tamagotchi-like personality. Scans networks, identifies hosts and open ports, performs service enumeration, and displays findings on an e-Paper display and web dashboard. Modular architecture with custom action scripts. Designed for Pi Zero W/W2 with 2.13" e-Paper HAT.

**Why it's useful:**
- Network reconnaissance — discover all devices on the LAN automatically
- Service enumeration reveals what's running on nearby devices
- Modular action system could be adapted for defensive monitoring
- Web dashboard pattern similar to ours — could borrow UI ideas
- e-Paper display integration is a cool secondary output option

**Integration approach:**
- Borrow the network scanning and host discovery modules as a new DataSource
- Display discovered LAN devices in a network map card on the dashboard
- Defensive only — use scanning for awareness, not exploitation
- Could feed into presence detection (which devices are home?)

**Hardware needed:**
- Already have Pi 3B+ with network access
- Optional: 2.13" e-Paper HAT for secondary display

**Depends on:** Nmap, Python networking libraries

---

## 13. rpitx — RF Transmitter via GPIO

**Repo:** https://github.com/F5OEO/rpitx
**Status:** Not started

Software-defined RF transmitter using Raspberry Pi GPIO. Transmits across 5 KHz to 1500 MHz with just a wire on GPIO4 — no additional hardware. Supports FM (with RDS), SSB, SSTV, POCSAG pager, FreeDV digital voice, chirp, and carrier modes. Can record and replay RF signals. Written in C/C++/Assembly.

**Why it's useful:**
- RF spectrum awareness — detect and analyze radio signals in the environment
- Could build a simple spectrum analyzer display for the dashboard
- SSTV (slow-scan TV) could send dashboard screenshots over radio
- POCSAG pager support — receive/display pager messages
- Educational — understand the RF environment around the Pi

**Integration approach:**
- Use the receive/transponder mode to monitor RF activity as a new DataSource
- Display RF activity level or detected signals on the dashboard
- SSTV integration — periodically broadcast a dashboard snapshot image
- Need RTL-SDR dongle for receive while transmitting

**Hardware needed:**
- Wire antenna on GPIO4 (trivial)
- Optional: RTL-SDR dongle for receive capability
- IMPORTANT: Transmitting without a filter can cause interference — use with caution and appropriate filtering

**Depends on:** C compiler, GPIO access, optional RTL-SDR libraries

---

## 14. P4wnP1 — USB Attack Platform (Defensive Reference)

**Repo:** https://github.com/RoganDawes/P4wnP1
**Status:** Not started

USB attack platform that emulates keyboards, mass storage, and network adapters simultaneously. Designed for Pi Zero but architecturally interesting for understanding USB HID attacks, covert channels, and device emulation. Bash/PowerShell/C# codebase.

**Why it's useful:**
- Understanding USB attack vectors helps build defensive monitoring
- HID injection detection — alert when unexpected USB keyboard input occurs
- USB device emulation patterns applicable to building custom USB gadgets
- Network-over-USB (RNDIS) is useful for headless Pi connectivity
- DuckyScript parser could be adapted for dashboard automation macros

**Integration approach:**
- Study USB HID attack patterns to build a defensive USB monitor
- Alert card: "Unexpected USB HID device connected" or "Rapid keystroke injection detected"
- Borrow the USB gadget configuration for Pi Zero connectivity options
- Reference only for attack techniques — implement detection, not exploitation

**Hardware needed:**
- Pi Zero W for USB gadget mode (Pi 3B+ doesn't support USB device mode)
- Or: just reference the codebase for defensive patterns on existing hardware

**Depends on:** USB gadget mode (Pi Zero only), bash

---

## 15. PiAware — ADS-B Flight Tracking

**Repo/Site:** https://uk.flightaware.com/adsb/piaware/install
**Also see:** https://github.com/cyoung/stratux (open-source alternative)
**Status:** Not started

FlightAware's PiAware turns a Pi into an ADS-B receiver that tracks aircraft overhead in real time. Decodes Mode S transponder signals from planes, reports position, altitude, speed, callsign, and aircraft type. Feeds data to FlightAware (free premium account in exchange) and provides a local web interface at port 8080.

**Why it's useful:**
- "What's flying overhead right now?" is a genuinely interesting ambient data source
- Real-time aircraft positions, altitudes, speeds on the dashboard
- Track flight patterns over your area throughout the day
- FlightAware gives a free Enterprise account for feeding data
- Local SkyAware web UI at port 8080 with map visualization

**Integration approach:**
- New DataSource polling the local PiAware API (JSON at `localhost:8080/data/aircraft.json`)
- Dashboard card showing: planes overhead count, closest aircraft, highest altitude
- Could overlay flight paths on a mini map
- Tap for detail overlay with full aircraft list

**Hardware needed:**
- RTL-SDR USB dongle (~$25) — receives 1090MHz ADS-B signals
- Small antenna (often included with RTL-SDR kits)
- Already have Pi 3B+ with USB port available

**Depends on:** dump1090 (ADS-B decoder), RTL-SDR drivers

---

## 16. Rhasspy — Offline Voice Assistant

**Repo:** https://rhasspy.readthedocs.io
**Status:** Not started

Complete offline voice assistant toolkit. Handles wake word detection, speech-to-text, intent recognition, and text-to-speech — all running locally without cloud services. Supports multiple STT backends (Vosk, DeepSpeech, Kaldi). Web interface for configuration. MQTT integration for home automation.

**Why it's useful:**
- Full offline voice pipeline when VPS is unreachable
- Intent recognition maps speech to structured commands (not just raw text)
- Wake word support — "Hey Geepers" without a button press
- MQTT output integrates with home automation and our event bus
- Manages audio hardware (ALSA/PulseAudio) configuration

**Integration approach:**
- Use as the on-Pi fallback when VPS Whisper is unreachable
- Borrow intent recognition patterns for structured voice commands
- "Set temperature alert to 30 degrees" → parsed intent, not free-form LLM query
- Could run alongside our browser-based voice for a hybrid approach

**Hardware needed:**
- Already have Pi 3B+ with Brio 100 mic
- Needs ~500MB for models

**Depends on:** Python, MQTT (optional), audio drivers

---

## 17. Pi-hole / AdGuard Home — DNS Monitoring

**Repo:** https://pi-hole.net/ / https://github.com/AdguardTeam/AdGuardHome
**Status:** Not started

Network-wide DNS sinkhole that blocks ads and trackers at the DNS level. Every device on the network benefits without any client-side software. Provides detailed query logs, statistics, and a web dashboard showing DNS request patterns.

**Why it's useful:**
- DNS query stats as a dashboard data source — see network activity patterns
- Block count, query count, top domains, top clients as ambient info
- "Your network blocked 2,847 ads today" is satisfying dashboard content
- Reveals which devices are most active and what they're phoning home to
- Already exists as a mature Pi project with API

**Integration approach:**
- New DataSource polling Pi-hole API (`/admin/api.php?summaryRaw`)
- Dashboard card: queries today, blocked %, top client, top domain
- Detail overlay with hourly query graph
- AdGuard Home has a cleaner REST API if we go that route

**Hardware needed:**
- Already have Pi 3B+ — Pi-hole is lightweight
- Needs to be configured as network DNS server (router setting)

**Depends on:** dnsmasq or unbound, network DNS configuration

---

## 18. Pwnagotchi — WiFi Environment Monitor

**Repo:** https://github.com/evilsocket/pwnagotchi
**Status:** Not started

Tamagotchi-like device that passively monitors WiFi traffic and learns about the wireless environment. Uses bettercap for packet capture and has a personality system that evolves based on WiFi activity. e-Paper display with cute face expressions. Plugin system for extensibility.

**Why it's useful:**
- Passive WiFi environment awareness — how many networks, signal quality trends
- Personality/gamification patterns applicable to our dashboard
- Plugin architecture is well-designed and worth studying
- The "mood" system based on environmental data is a creative UI concept
- Could feed WiFi environment quality metrics into our dashboard

**Integration approach:**
- Study the personality/mood system for dashboard gamification ideas
- Borrow WiFi analysis patterns for richer WiFi scanner data
- The "face" concept — dashboard could show a mood based on sensor readings
- Plugin architecture patterns applicable to our DataSource system

**Hardware needed:**
- Needs monitor mode WiFi adapter (Pi built-in doesn't support this well)
- Or: reference architecture only, borrow ideas

**Depends on:** bettercap, monitor-mode WiFi adapter

---

## 19. motionEyeOS / speed-camera — Enhanced Camera

**Repo:** https://github.com/ccrisan/motioneyeos/wiki / https://github.com/pageauc/speed-camera
**Status:** Not started

motionEyeOS is a full surveillance system OS with motion detection, recording, streaming, and notifications. speed-camera tracks object motion with speed estimation using Pi camera or USB webcam. Both provide web interfaces.

**Why it's useful:**
- We already have a USB webcam (Brio 100) with basic motion detection
- Motion zone configuration — trigger alerts only when specific areas change
- Speed estimation from pixel displacement — useful for vehicle/pet tracking
- Recording and timelapse features
- Notification hooks (email, webhook) when motion detected

**Integration approach:**
- Borrow advanced motion detection algorithms for our CameraSource
- Add motion zone support (define regions of interest in the frame)
- Speed/velocity estimation from frame differencing
- Could run motionEye as a separate service and pull events into our dashboard

**Hardware needed:**
- Already have Brio 100 USB webcam
- Already doing basic motion detection

**Depends on:** ffmpeg (already installed), motion library

---

## 20. Magic Mirror — Modular Dashboard Patterns

**Repo:** http://magicmirror.builders / https://github.com/MichMich/MagicMirror
**Status:** Not started (reference architecture)

Modular smart mirror platform with 3000+ community modules. Electron-based, runs on Pi. Module system with standardized lifecycle, DOM manipulation, and socket notifications. Modules for weather, calendar, news, transit, Spotify, and hundreds more.

**Why it's useful:**
- Massive module ecosystem with patterns we could adapt
- Calendar integration, transit times, Spotify now-playing
- Module lifecycle pattern (start → loaded → dom created → data received)
- Socket notification system similar to our EventBus
- CSS position system for arranging modules on screen

**Integration approach:**
- Study the module architecture for ideas on making our card system more pluggable
- Port popular module concepts: calendar, transit, Spotify, news ticker
- Borrow the "position" system for more flexible card placement
- Community modules as inspiration for new DataSources

**Hardware needed:**
- N/A (reference architecture, borrow patterns)

**Depends on:** N/A (reference only)

---

## 21. Pi-KVM — Remote Hardware Control

**Repo:** https://github.com/pikvm/pikvm
**Status:** Not started

Full KVM-over-IP solution for Raspberry Pi. Provides remote keyboard, video, and mouse control of another computer via web browser. Supports HDMI capture, virtual USB HID, ATX power control, and IPMI/Redfish. Web UI with VNC-like interface.

**Why it's useful:**
- Remote access to the Pi's display without physical presence
- Could debug the kiosk display remotely
- IPMI-like power management for the Pi itself
- Web-based VNC pattern useful for remote dashboard administration

**Integration approach:**
- Not a dashboard data source, but useful infrastructure
- Remote management of the kiosk Pi from the VPS
- Could embed a mini KVM view in an admin panel

**Hardware needed:**
- Pi 4 or Pi 5 recommended (Pi 3 has limitations)
- HDMI capture dongle for viewing other machines

**Depends on:** USB gadget mode support

---

## 22. GOES-16 / RTL-SDR — Weather Satellite Imagery

**Reference:** https://gist.github.com/lxe/c1756ca659c3b78414149a3ea723eae2
**Status:** Not started

Receive weather satellite imagery directly from GOES-16/17 geostationary weather satellites using an RTL-SDR dongle and small dish antenna. Produces high-resolution cloud imagery, infrared temperature maps, and storm tracking data updated every 15 minutes.

**Why it's useful:**
- Direct weather satellite imagery on the dashboard — no internet required
- Real cloud cover photos of your actual area from space
- Infrared imagery shows temperature patterns
- Combined with ground sensors = comprehensive weather picture
- Same RTL-SDR dongle as PiAware (dual use)

**Integration approach:**
- New DataSource that captures and processes satellite images
- Display latest satellite image as a dashboard card
- Overlay indoor sensor data on the satellite view
- Could automate image capture on a schedule

**Hardware needed:**
- RTL-SDR dongle (same as PiAware, #15)
- Small satellite dish or patch antenna (GOES is geostationary)
- LNA (low noise amplifier) recommended

**Depends on:** goestools or similar decoder, RTL-SDR drivers

---

# API-Powered Features (dr.eamer.dev)

These features leverage the existing API gateway at api.dr.eamer.dev to bring rich data into the dashboard without additional hardware.

---

## 23. NASA APOD Screensaver

**API Endpoint:** `api.dr.eamer.dev/v1/data/nasa`
**Status:** Not started

Use NASA's Astronomy Picture of the Day as an ambient screensaver when the dashboard is idle. Full-screen stunning space imagery with caption overlay. Rotates through recent APODs or shows today's image.

**Integration approach:**
- Fetch APOD via existing NASA data source on the API gateway
- Display as fullscreen background when dashboard goes idle (no interaction for 5+ min)
- Subtle sensor readout overlay on the image
- Tap anywhere to return to normal dashboard

**Hardware needed:** None (API-powered)

---

## 24. News Ticker

**API Endpoint:** `api.dr.eamer.dev/v1/utilities/news/headlines`
**Status:** Not started

Scrolling news headline ticker across the bottom or top of the dashboard. Pull headlines from the news API, display as a scrolling marquee or rotating card. Configurable sources and categories.

**Integration approach:**
- New DataSource polling news API every 15-30 minutes
- Scrolling ticker in the header bar or dedicated slim card
- Tap a headline to ask the LLM chat about it
- Category filtering (tech, science, local)

**Hardware needed:** None (API-powered)

---

## 25. Word of the Day / Etymology

**API Endpoint:** `api.dr.eamer.dev/v1/etymology/explore/<word>`
**Status:** Not started

Display an interesting word with its etymology, language of origin, and related cognates. Rotates daily. Tapping shows the full etymology tree and related words.

**Integration approach:**
- Daily word selection (curated list or random interesting words)
- Small card showing word, origin language, brief meaning
- Tap for etymology detail overlay from the API
- Could tie into corpus frequency data from COCA

**Hardware needed:** None (API-powered)

---

## 26. LLM Image Generation — Dynamic Art

**API Endpoint:** `api.dr.eamer.dev/v1/llm/image/generate`
**Status:** Not started

Generate ambient artwork based on current sensor readings. "A cozy room at 22°C with 45% humidity on a cloudy evening" → unique generated image as dashboard background or screensaver. Changes as conditions change.

**Integration approach:**
- Periodically generate images from sensor context (hourly or on significant change)
- Use as screensaver/background alongside or instead of NASA APOD
- Cache generated images to avoid redundant API calls
- Provider: xAI Aurora or OpenAI DALL-E via the gateway

**Hardware needed:** None (API-powered)

---

## 27. Wolfram Alpha — Smart Calculations

**API Endpoint:** `api.dr.eamer.dev/v1/data/wolfram`
**Status:** Not started

Integrate Wolfram Alpha computational knowledge for enriching sensor data. "What's the dew point at 22°C and 55% humidity?" "How does UV index 6 compare to typical for this latitude?" Contextual science facts based on current readings.

**Integration approach:**
- Enrich chat responses with computational data
- Auto-calculate derived values: dew point, heat index, wind chill
- "Did you know?" facts triggered by sensor readings
- Could power a science/education mode for the dashboard

**Hardware needed:** None (API-powered)

---

## 28. Wikipedia Context Cards

**API Endpoint:** `api.dr.eamer.dev/v1/data/wikipedia`
**Status:** Not started

Surface relevant Wikipedia snippets based on sensor readings or user queries. "VOC index is 250 — learn about volatile organic compounds." Air quality alerts link to health guidance articles. Weather events link to meteorological explanations.

**Integration approach:**
- Contextual knowledge cards triggered by sensor thresholds
- "Learn more" links in alert messages
- Enrich the LLM chat with Wikipedia context
- Daily random interesting fact related to weather/environment

**Hardware needed:** None (API-powered)
