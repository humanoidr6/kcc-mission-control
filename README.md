# KCC Mission Control & Satellite Telemetry Node

This repository contains the complete software stack for the **KCC Mission Control** ground station and the **Satellite Telemetry Node** built on a Teensy 4.1.

## 🛰️ Architecture Overview

1. **Satellite Node (Teensy 4.1):** Reads data from onboard sensors (Temperature, Humidity, Light, and 6-DOF IMU) and broadcasts it over a 433MHz LoRa radio link using CCSDS-like packets.
2. **Ground Station Receiver (RTL-SDR):** An RTL-SDR dongle captures the 433MHz radio waves, and GNU Radio (`start_lora.py`) demodulates the raw LoRa physical layer back into binary data.
3. **Pipe & Backend (`pipe_lora.py` & `app.py`):** The binary stream is piped via UDP to a Python Flask backend which parses the 33-byte telemetry structures and serves them to the frontend.
4. **Mission Control Dashboard:** A beautiful web interface displaying live graphs, 3D IMU visualizations, and real-time sensor metrics.

---

## 🛠️ Hardware Requirements & Wiring

### 1. Satellite Node
- **Microcontroller:** Teensy 4.1
- **Radio:** LoRa RA-02 (433MHz SPI)
- **IMU:** MPU6050 (or cloned MPU9250 acting as 6050)
- **Environment:** DHT11 Temp/Humidity Sensor
- **Light:** LDR (Photoresistor) + 10k pull-down resistor

#### 🔌 Wiring Guide
**LoRa RA-02 (SPI):**
- `NSS` (CS) -> **Pin 10**
- `RST` (Reset) -> **Pin 9**
- `DIO0` (Interrupt) -> **Pin 2**
- `MOSI` -> **Pin 11**
- `MISO` -> **Pin 12**
- `SCK` -> **Pin 13**
- `3.3V` & `GND`

**MPU6050 (I2C):**
- `SDA` -> **Pin 18**
- `SCL` -> **Pin 19**
- `3.3V` & `GND`

**DHT11:**
- `DATA` -> **Pin 4**
- `3.3V` & `GND`
- *(Note: Ensure a 4.7kΩ or 10kΩ pull-up resistor is between DATA and 3.3V if using a bare sensor!)*

**LDR:**
- One leg to `3.3V`
- Other leg to **Pin A0** and a 10kΩ resistor to `GND`.

---

## 🚀 Step-by-Step Guide

### Part 1: Flashing the Satellite Node
1. Install the Arduino IDE and the Teensyduino add-on.
2. Open `Teensy_Node_Firmware/KCC_Teensy_Node.ino`.
3. Open the Library Manager and install:
   - `LoRa` by Sandeep Mistry
   - `Adafruit MPU6050` (and its dependency `Adafruit Unified Sensor`)
   - `DHT sensor library` by Adafruit
4. Select **Teensy 4.1** in the tools menu.
5. Compile and Upload. Ensure the Serial Monitor says `LoRa Initialization OK!`.

### Part 2: Starting the Ground Station
1. Plug in your RTL-SDR USB Dongle.
2. Install the necessary Python dependencies:
   ```bash
   pip install flask flask-socketio
   ```
   *(Note: GNU Radio and `gr-lora_sdr` must also be installed system-wide for the SDR to work).*
3. Run the Mission Control launcher:
   ```bash
   python3 launcher.py
   ```
4. The backend will automatically start the SDR listener and pipe scripts. Open your web browser to `http://127.0.0.1:5000` to view the dashboard!

---

## ⚠️ Important Precautions & Quirks

1. **Fake MPU9250s (Clones):** The vast majority of MPU9250 chips sold online are actually older MPU6050 chips relabeled. This firmware is configured to use the `Adafruit_MPU6050` library to ensure flawless compatibility. Because it is a 6050, magnetometer (compass) values will read `0`.
2. **IMU Dashboard Sensitivity:** The firmware scales the gravity vectors by `16384` (the 16-bit raw ADC resolution for ±2G) before transmitting, ensuring the 3D dashboard model is highly responsive.
3. **LoRa Breadboard Interference:** The SPI frequency is intentionally downclocked to `1MHz` (`LoRa.setSPIFrequency(1000000)`). High-speed SPI on breadboard jumper wires degrades signal integrity and causes the LoRa chip to fail initialization.
4. **DHT11 Crash Loop:** DHT11 sensors will hard-crash if polled faster than once every 2 seconds. The firmware utilizes a non-blocking `millis()` timer to safely poll the DHT11 while simultaneously maintaining a high-speed telemetry broadcast.
5. **SDR Lockups:** If you abruptly kill the Python app, the RTL-SDR may remain locked by a ghost background process (`usb_claim_interface error -6`). If this happens, use `pkill -f start_lora` or simply re-plug the USB dongle.
