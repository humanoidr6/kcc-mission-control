#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <DHT.h>

// Pins
#define LORA_CS    10
#define LORA_RST   9
#define LORA_DIO0  2
#define LDRPIN     A0
#define DHTPIN     3
#define DHTTYPE    DHT11

#define LORA_FREQ  440E6

DHT dht(DHTPIN, DHTTYPE);

bool mpu_found = false;
uint8_t mpu_addr = 0x68;

float lastTemp = 0.0;
float lastHum = 0.0;
unsigned long lastDHTRead = 0;

// A ~75-byte packet at SF7/125kHz is ~140ms on air. Sending faster than that
// used to pile several payloads into one packet, so pace below the airtime.
#define TX_INTERVAL_MS 250
unsigned long lastTx = 0;
unsigned long seq = 0;

// ---- Unattended (battery) operation -----------------------------------------
// No laptop means nobody to press reset, so the node heals itself:
//  - a software watchdog reboots the Teensy if loop() stops running,
//  - the radio is re-initialised if it stops accepting packets, or if its
//    frequency register no longer holds 440 MHz (a supply dip can reset the
//    SX1278 back to its 434 MHz defaults while the Teensy keeps running).
#define WATCHDOG_MS        8000
#define RADIO_STUCK_MS     2000
#define RADIO_CHECK_MS     5000
#define REG_FRF_MSB        0x06

IntervalTimer watchdogTimer;
volatile uint32_t lastFeed = 0;
unsigned long lastRadioOk = 0;
unsigned long lastRadioCheck = 0;

void watchdogIsr() {
  if (millis() - lastFeed > WATCHDOG_MS) {
    SCB_AIRCR = 0x05FA0004;  // system reset
  }
}

uint8_t radioReadReg(uint8_t reg) {
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(LORA_CS, LOW);
  SPI.transfer(reg & 0x7F);
  uint8_t v = SPI.transfer(0x00);
  digitalWrite(LORA_CS, HIGH);
  SPI.endTransaction();
  return v;
}

uint8_t expectedFrfMsb() {
  uint64_t frf = ((uint64_t)LORA_FREQ << 19) / 32000000;
  return (uint8_t)(frf >> 16);
}

bool radioInit() {
  // Reset LoRa
  pinMode(LORA_RST, OUTPUT);
  digitalWrite(LORA_RST, LOW);
  delay(100);
  digitalWrite(LORA_RST, HIGH);
  delay(100);

  if (!LoRa.begin(LORA_FREQ)) return false;
  LoRa.setTxPower(20);
  LoRa.setSpreadingFactor(7);
  LoRa.setSignalBandwidth(125E3);
  LoRa.enableCrc();
  lastRadioOk = millis();
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("KCC Full Sensor Node Starting...");

  pinMode(LDRPIN, INPUT);
  analogReadResolution(12);
  dht.begin();
  Wire.begin();

  // RAW I2C IMU INITIALIZATION (Bypasses Who-Am-I checks)
  Wire.beginTransmission(0x68);
  if (Wire.endTransmission() == 0) {
    mpu_found = true;
    mpu_addr = 0x68;
    Serial.println("IMU found at 0x68!");
  } else {
    Wire.beginTransmission(0x69);
    if (Wire.endTransmission() == 0) {
      mpu_found = true;
      mpu_addr = 0x69;
      Serial.println("IMU found at 0x69!");
    } else {
      Serial.println("IMU not found! (Will skip reading it)");
    }
  }

  if (mpu_found) {
    // Wake up the IMU
    Wire.beginTransmission(mpu_addr);
    Wire.write(0x6B); // PWR_MGMT_1
    Wire.write(0x00); // Wake up
    Wire.endTransmission();
  }

  SPI.begin();
  LoRa.setSPI(SPI);
  LoRa.setSPIFrequency(1000000);
  LoRa.setPins(LORA_CS, LORA_RST, LORA_DIO0);

  // On battery the radio can be slower to come up than the Teensy; keep
  // trying, and reboot everything if it never does.
  int tries = 0;
  while (!radioInit()) {
    Serial.println("Starting LoRa failed! Check wiring!");
    if (++tries >= 15) SCB_AIRCR = 0x05FA0004;
    delay(1000);
  }

  Serial.println("LoRa is ready at 440MHz! Sending telemetry every " + String(TX_INTERVAL_MS) + "ms");

  lastFeed = millis();
  watchdogTimer.begin(watchdogIsr, 500000);  // check every 0.5 s
}

void checkRadio() {
  bool stuck = millis() - lastRadioOk > RADIO_STUCK_MS;
  bool reset = false;
  if (millis() - lastRadioCheck >= RADIO_CHECK_MS) {
    lastRadioCheck = millis();
    reset = radioReadReg(REG_FRF_MSB) != expectedFrfMsb();
  }
  if (stuck || reset) {
    Serial.println(stuck ? "Radio stuck, re-initialising" : "Radio lost its settings, re-initialising");
    radioInit();
  }
}

void loop() {
  lastFeed = millis();

  if (millis() - lastDHTRead >= 2000) {
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t)) lastTemp = t;
    if (!isnan(h)) lastHum = h;
    lastDHTRead = millis();
  }

  checkRadio();

  if (millis() - lastTx < TX_INTERVAL_MS) return;

  // beginPacket() returns 0 while the previous async packet is still on air;
  // writing anyway is what appended payloads into the same packet before.
  if (!LoRa.beginPacket()) return;
  lastTx = millis();
  lastRadioOk = lastTx;

  int ldr = analogRead(LDRPIN);

  String payload = "Temp:" + String(lastTemp) + " Hum:" + String(lastHum) + " LDR:" + String(ldr) + " ";

  if (mpu_found) {
    // RAW I2C ACCEL X/Y/Z READ (6 bytes from ACCEL_XOUT_H)
    Wire.beginTransmission(mpu_addr);
    Wire.write(0x3B); // ACCEL_XOUT_H
    Wire.endTransmission(false);
    Wire.requestFrom((uint8_t)mpu_addr, (uint8_t)6, (uint8_t)true);
    if (Wire.available() == 6) {
      int16_t ax_raw = Wire.read() << 8 | Wire.read();
      int16_t ay_raw = Wire.read() << 8 | Wire.read();
      int16_t az_raw = Wire.read() << 8 | Wire.read();
      // Default sensitivity is +/- 2g
      payload += "AccelX:" + String(ax_raw / 16384.0) + " ";
      payload += "AccelY:" + String(ay_raw / 16384.0) + " ";
      payload += "AccelZ:" + String(az_raw / 16384.0) + " ";
    }
  }

  payload += "Seq:" + String(seq++);

  // Debug Print so I can see it! (Harmless without USB: Teensy drops it.)
  Serial.println(payload);

  LoRa.print(payload);
  LoRa.endPacket(true);
}
