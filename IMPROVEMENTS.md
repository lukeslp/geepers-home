# Sensor Playground — Improvement Plan

## Analysis Summary

The codebase is solid: clean sensor interface, config-driven UI, proper GPIO abstraction.
Below are the improvements to implement.

## 1. Add a proper README.md
- Project overview, screenshots placeholder, features, setup, usage, architecture
- Sensor table with all 18 sensors, pin assignments, categories

## 2. Improve error handling and resilience
- Add retry logic for DHT11 (known flaky sensor)
- Wrap all sensor reads in try/except in the poll loop to prevent one sensor crash from affecting others
- Add sensor reconnection attempts for GPIO failures
- Batch CSV writes to reduce SD card wear

## 3. UI/UX improvements
- Add min/max/avg statistics display on the left panel
- Add a timestamp to the graph X-axis
- Add graph fill/gradient under line traces for better visual appeal
- Improve the INFO tab with a scrollbar
- Add a "connected sensors" count to the status bar
- Add keyboard shortcuts display

## 4. Code quality improvements
- Add type hints throughout
- Add a base sensor class (ABC) to formalize the interface
- Reduce code duplication in digital sensor modules (they're nearly identical)
- Add logging module instead of print statements

## 5. New features
- Add an export function (export current graph as PNG)
- Add sensor alerts/thresholds (configurable high/low alerts)
- Add a system info panel (CPU temp, memory, uptime)
- Add auto-demo cycling through sensors (kiosk mode)

## 6. Setup and deployment
- Add requirements.txt
- Improve setup.sh with better error handling
- Add a systemd service file for auto-start on boot
