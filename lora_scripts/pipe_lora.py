#!/usr/bin/env python3
import subprocess
import socket
import re
import time

UDP_IP = "127.0.0.1"
UDP_PORT = 52001

print("Starting pipe wrapper...")
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

import os
env = os.environ.copy()
env["PYTHONPATH"] = "/usr/local/lib/python3.14/dist-packages:" + env.get("PYTHONPATH", "")

while True:
    print("Listening for packets from GNURadio...")
    
    # Start start_lora.py in unbuffered mode!
    process = subprocess.Popen(
        ["python3", "-u", "/home/spirit/start_lora.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=False,
        bufsize=0,
        env=env
    )
    
    buffer = b""
    while True:
        chunk = process.stdout.read(1)
        if not chunk:
            break
        buffer += chunk
        
        # Check if we have the prefix
        idx = buffer.find(b"rx msg: ")
        if idx != -1:
            # We found the start of a packet!
            if len(buffer) >= idx + 8 + 33:
                payload = buffer[idx+8 : idx+8+33]
                
                # Send EXACTLY the 33-byte payload directly to the UDP listener!
                sock.sendto(payload, (UDP_IP, UDP_PORT))
                print(f"-> Forwarded packet to Dashboard (33 bytes)")
                
                # Remove this processed packet from the buffer
                buffer = buffer[idx+8+33:]
            elif len(buffer) > 1024:
                buffer = buffer[-1024:]
        else:
            if len(buffer) > 1024:
                buffer = buffer[-1024:]

    print("GNURadio process died! Restarting in 2 seconds...")
    process.wait()
    time.sleep(2)
