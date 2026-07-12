#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <DHT.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// ==========================================
// PINS CONFIGURATION (Teensy 4.1)
// ==========================================

#define LORA_CS    10  
#define LORA_RST   9   
#define LORA_DIO0  2   

#define DHTPIN     4   
#define DHTTYPE    DHT11 

#define LDRPIN     A0  

DHT dht(DHTPIN, DHTTYPE);
Adafruit_MPU6050 mpu;

#pragma pack(push, 1) 
struct TelemetryPacket {
  uint16_t word1;
  uint16_t word2;
  uint16_t length;
  float temperature;
  float humidity;
  uint8_t ldr;
  int16_t accelX;
  int16_t accelY;
  int16_t accelZ;
  int16_t gyroX;
  int16_t gyroY;
  int16_t gyroZ;
  int16_t magX;
  int16_t magY;
  int16_t magZ;
} packet;
#pragma pack(pop)

uint16_t seq_count = 0;

void setup() {
  Serial.begin(115200);
  
  uint32_t t = millis();
  while (!Serial && (millis() - t < 3000));
  
  Serial.println("KCC Mission Control - Sensor Node starting (Adafruit MPU6050 fallback)...");

  dht.begin();
  pinMode(LDRPIN, INPUT);

  Wire.begin();
  
  if (!mpu.begin()) {
    Serial.println("Failed to find MPU6050 chip! Wiring issue or dead chip.");
  } else {
    Serial.println("MPU6050 (Clone) Initialized successfully!");
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  }

  // FORCE A VERY LONG HARD RESET FOR THE LORA MODULE
  pinMode(LORA_RST, OUTPUT);
  digitalWrite(LORA_RST, LOW);
  delay(100);  
  digitalWrite(LORA_RST, HIGH);
  delay(100);  

  SPI.begin();
  LoRa.setSPI(SPI);
  LoRa.setSPIFrequency(1000000); 
  LoRa.setPins(LORA_CS, LORA_RST, LORA_DIO0);
  
  if (!LoRa.begin(433E6)) {
    Serial.println("Starting LoRa failed! Check SPI wiring!");
  } else {
    LoRa.setSpreadingFactor(7);
    LoRa.setSignalBandwidth(125E3);
    LoRa.enableCrc();
    Serial.println("LoRa Initialization OK!");
  }
}

void loop() {
  static float lastTemp = 0.0;
  static float lastHum = 0.0;
  static uint32_t lastDHTTime = 0;
  
  // DHT11 sensors crash if you read them faster than once every 2 seconds!
  if (millis() - lastDHTTime >= 2000 || lastDHTTime == 0) {
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t)) lastTemp = t;
    if (!isnan(h)) lastHum = h;
    lastDHTTime = millis();
  }

  float temp = lastTemp;
  float hum = lastHum;

  int ldrRaw = analogRead(LDRPIN);
  uint8_t ldrValue = (ldrRaw > 512) ? 1 : 0; 

  sensors_event_t a, g, temp_event;
  mpu.getEvent(&a, &g, &temp_event);

  // Adafruit returns accel in m/s^2. 
  // We divide by 9.81 to get Gs, then multiply by 16384 to match raw 16-bit sensor values (which the dashboard expects).
  int16_t ax = (a.acceleration.x / 9.81) * 16384.0;
  int16_t ay = (a.acceleration.y / 9.81) * 16384.0;
  int16_t az = (a.acceleration.z / 9.81) * 16384.0;
  
  // Adafruit returns gyro in rad/s.
  // We convert to deg/s, then multiply by 131.0 to match raw 16-bit sensor values.
  int16_t gx = (g.gyro.x * 57.2958) * 131.0;
  int16_t gy = (g.gyro.y * 57.2958) * 131.0;
  int16_t gz = (g.gyro.z * 57.2958) * 131.0;
  
  // Clone MPU6050 doesn't have a magnetometer. Sending 0.
  int16_t mx = 0;
  int16_t my = 0;
  int16_t mz = 0;

  uint16_t apid = 123;
  packet.word1 = __builtin_bswap16(0x0000 | apid);
  packet.word2 = __builtin_bswap16(0xC000 | (seq_count & 0x3FFF));
  packet.length = __builtin_bswap16(26); 

  packet.temperature = temp;
  packet.humidity = hum;
  packet.ldr = ldrValue;
  
  packet.accelX = ax;
  packet.accelY = ay;
  packet.accelZ = az;
  packet.gyroX = gx;
  packet.gyroY = gy;
  packet.gyroZ = gz;
  packet.magX = mx; 
  packet.magY = my;
  packet.magZ = mz;

  LoRa.beginPacket();
  LoRa.write((uint8_t*)&packet, sizeof(packet));
  LoRa.endPacket();

  Serial.print("Packet Sent! Temp: ");
  Serial.print(temp);
  Serial.print(" AccelZ: ");
  Serial.print(az);
  Serial.print(" Seq: ");
  Serial.println(seq_count);
  
  seq_count++;
  delay(1000);
}
