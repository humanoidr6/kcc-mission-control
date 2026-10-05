#!/usr/bin/env python3
"""Pretend to be the ESP32 ground station, for testing the website without hardware.

Publishes frames in exactly the JSON shape ESP32_LoRa_Receiver.ino sends, to the
same MQTT topic, so https://humanoidr6.github.io/kcc-website/telemetry.html
goes live. Nothing is retained, so the broker keeps no fake data after you stop.

    pip install paho-mqtt
    python3 fake_ground_station.py            # 4 frames/s until Ctrl+C
    python3 fake_ground_station.py --count 40
"""
import argparse
import json
import math
import random
import time

import paho.mqtt.client as mqtt

BROKER = "broker.hivemq.com"
TOPIC_BASE = "kcc-cu/node01-29e8ea47"  # must match the ESP32 and telemetry.js


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=0, help="frames to send (0 = forever)")
    ap.add_argument("--rate", type=float, default=4.0, help="frames per second")
    args = ap.parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"kcc-fake-gs-{random.randrange(1 << 32):08x}")
    client.connect(BROKER, 1883, keepalive=30)
    client.loop_start()
    client.publish(f"{TOPIC_BASE}/status", "online").wait_for_publish()

    seq, pkts, temp, hum = 0, 0, 27.4, 58.0
    try:
        while args.count == 0 or pkts < args.count:
            t = time.time()
            if seq % 8 == 0:
                temp += random.uniform(-0.1, 0.1)
                hum += random.uniform(-0.3, 0.3)
            if random.random() < 0.03:
                seq += 1  # simulate a lost LoRa packet
            ax, ay = 0.05 * math.sin(t / 3), 0.04 * math.cos(t / 4)
            az = 0.98 + 0.03 * math.sin(t * 1.7)
            ldr = int(2100 + 900 * math.sin(t / 20) + random.uniform(-30, 30))
            raw = (f"Temp:{temp:.2f} Hum:{hum:.2f} LDR:{ldr} AccelX:{ax:.2f} "
                   f"AccelY:{ay:.2f} AccelZ:{az:.2f} Seq:{seq}")
            pkts += 1
            frame = {
                "ldr": ldr, "accelx": round(ax, 2), "accely": round(ay, 2), "accelz": round(az, 2),
                "temp": round(temp, 2), "hum": round(hum, 2),
                "rssi": random.randint(-62, -55), "snr": round(random.uniform(8.5, 10), 1),
                "seq": seq, "pkts": pkts, "ts": int(t * 1000), "cloud": True, "raw": raw,
            }
            client.publish(f"{TOPIC_BASE}/telemetry", json.dumps(frame))
            print(raw)
            seq += 1
            time.sleep(1 / args.rate)
    except KeyboardInterrupt:
        pass
    finally:
        client.publish(f"{TOPIC_BASE}/status", "offline").wait_for_publish()
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
