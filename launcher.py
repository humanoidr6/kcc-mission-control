#!/usr/bin/env python3
import os
import subprocess
import time
import signal
import sys

def cleanup(signum=None, frame=None):
    print("Shutting down Mission Control backend...")
    os.system("pkill -9 -f app.py")
    os.system("pkill -9 -f start_lora")
    os.system("pkill -9 -f pipe_lora")
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

# ALWAYS cleanup before starting to free up the RTL-SDR dongle!
print("Cleaning up old processes...")
os.system("pkill -9 -f app.py")
os.system("pkill -9 -f start_lora")
os.system("pkill -9 -f pipe_lora")
time.sleep(1)

print("Starting Mission Control Backend...")
# Start Flask App
flask_log = open("/tmp/app_debug.log", "w")
flask_process = subprocess.Popen(
    ["./venv/bin/python", "-u", "app.py"],
    cwd="/home/spirit/mission_control",
    stdout=flask_log,
    stderr=subprocess.STDOUT,
    start_new_session=True
)

# Start LoRa Pipe
lora_log = open("/tmp/lora_debug.log", "w")
lora_process = subprocess.Popen(
    ["python3", "-u", "/home/spirit/pipe_lora.py"],
    cwd="/home/spirit",
    stdout=lora_log,
    stderr=subprocess.STDOUT,
    start_new_session=True
)

print("Waiting for backend services to spin up completely...")
time.sleep(5)

print("Launching Application Interface...")
# Launch Chrome in App Mode (it will likely detach and return immediately)
os.system("google-chrome --app=http://127.0.0.1:5000 --window-size=1400,900 &")

print("Backend is running in the background. Close the terminal/launcher.")
sys.exit(0)
