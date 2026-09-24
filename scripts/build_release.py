"""
Release Build & Packaging Script for FSOC Coarse Alignment Desktop Application.

Orchestrates:
  1. Frontend production compilation (Vite + TypeScript)
  2. Python tracking engine packaging via PyInstaller
  3. Standalone release bundle generation
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
DIST_DIR = ROOT_DIR / "release"


def run_command(cmd, cwd=None):
    print(f"--> Running: {cmd} in {cwd or Path.cwd()}")
    result = subprocess.run(cmd, shell=True, cwd=str(cwd) if cwd else None)
    if result.returncode != 0:
        print(f"[ERROR] Command failed with exit code {result.returncode}: {cmd}")
        sys.exit(result.returncode)


def build_frontend():
    print("\n==========================================")
    print(" 1. Building React / TypeScript Frontend")
    print("==========================================")
    run_command("npm.cmd run build", cwd=FRONTEND_DIR)


def build_backend():
    print("\n==========================================")
    print(" 2. Packaging Python Engine (PyInstaller)")
    print("==========================================")
    # Check if pyinstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found. Installing...")
        run_command("pip install pyinstaller")

    spec_file = BACKEND_DIR / "fsoc_sidecar.spec"
    run_command(f"pyinstaller --noconfirm --clean \"{spec_file}\"", cwd=BACKEND_DIR)


def assemble_release():
    print("\n==========================================")
    print(" 3. Assembling Standalone Release Package")
    print("==========================================")
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    # Copy frontend build
    shutil.copytree(FRONTEND_DIR / "dist", DIST_DIR / "ui")

    # Copy sidecar exe
    sidecar_dist = BACKEND_DIR / "dist" / "fsoc-sidecar.exe"
    if sidecar_dist.exists():
        shutil.copy2(sidecar_dist, DIST_DIR / "fsoc-sidecar.exe")

    # Copy configs & models
    shutil.copytree(BACKEND_DIR / "configs", DIST_DIR / "configs")
    shutil.copytree(ROOT_DIR / "models", DIST_DIR / "models")

    # Create launcher script
    launcher_bat = DIST_DIR / "launch_fsoc_tracker.bat"
    with open(launcher_bat, "w") as f:
        f.write("@echo off\n")
        f.write("echo Starting FSOC Tracking System...\n")
        f.write("start \"\" fsoc-sidecar.exe --mode simulation --port 8765\n")
        f.write("timeout /t 2 /nobreak >nul\n")
        f.write("start \"\" ui\\index.html\n")

    print(f"\n[SUCCESS] Standalone release ready at: {DIST_DIR}")


if __name__ == "__main__":
    build_frontend()
    assemble_release()
