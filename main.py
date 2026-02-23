#!/usr/bin/env python3
"""Sensor Playground — Entry point.

Launches the touchscreen GUI for reading and visualising sensor data.

Usage:
    python3 main.py              # Normal mode (reads real hardware)
    python3 main.py --demo       # Start with demo mode on
    python3 main.py --log-level DEBUG   # Verbose logging

Controls:
    DEMO   — Toggle simulated data (works without any sensors wired)
    LOG    — Start/stop CSV logging to data/ directory
    EXIT   — Quit the application
    Escape — Toggle fullscreen

Tap a sensor tab to view its readings and graph.
Tap the graph area to clear that sensor's history.
"""

__version__ = "3.0.0"

import argparse
import logging
import os
import sys

# Ensure we can import from the project directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk


def parse_args():
    parser = argparse.ArgumentParser(
        description="Sensor Playground — Raspberry Pi sensor dashboard",
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Start with demo mode enabled (simulated data)",
    )
    parser.add_argument(
        "--classic", action="store_true",
        help="Use the classic tab-based sensor browser",
    )
    parser.add_argument(
        "--legacy", action="store_true",
        help="Use the v2 single-page dashboard (before extensible cards)",
    )
    parser.add_argument(
        "--config", default="dashboard.yaml",
        help="Path to dashboard YAML config (default: dashboard.yaml)",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set the logging verbosity (default: INFO)",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"Sensor Playground {__version__}",
    )
    return parser.parse_args()


def setup_logging(level_name: str) -> None:
    """Configure root logger with a consistent format."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    args = parse_args()
    setup_logging(args.log_level)

    logger = logging.getLogger(__name__)
    logger.info("Sensor Playground v%s starting", __version__)

    print("Creating Tk root...", flush=True)
    root = tk.Tk()
    print(f"Tk root created: {root}", flush=True)

    if args.classic:
        print("Loading classic sensor browser...", flush=True)
        from ui.app import SensorPlayground
        app = SensorPlayground(root)
    elif args.legacy:
        print("Loading legacy dashboard...", flush=True)
        from ui.dashboard import EnvironmentDashboard
        app = EnvironmentDashboard(root)
    else:
        print("Loading Home Station v3...", flush=True)
        from ui.home_station import HomeStation
        app = HomeStation(root, config_path=args.config)
    print("App created successfully!")

    if args.demo:
        app._toggle_demo()

    print("Making window visible...")
    root.deiconify()
    root.lift()
    root.focus_force()

    print("Starting mainloop...")
    try:
        root.mainloop()
        print("Mainloop exited")
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        app.cleanup()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
