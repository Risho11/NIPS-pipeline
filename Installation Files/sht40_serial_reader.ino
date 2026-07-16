/*
 * Unified Arduino sketch: N2 blower + compression tester + SHT40 sensor
 *
 * Flash this ONCE from any PC with the Arduino IDE. After flashing,
 * the Arduino needs no further IDE/PC interaction - move it to the OT-2
 * and talk to it purely over serial (pyserial) from Python.
 *
 * This REPLACES StandardFirmata/pyfirmata entirely - only one sketch
 * can run on the Arduino at a time, so all pin control (blower, tester)
 * and the SHT40 read now happen through this single serial protocol.
 *
 * Wiring:
 *   Digital pin 12 (OUTPUT) -> compression tester trigger
 *   Digital pin 9  (INPUT)  -> compression tester status
 *   Digital pin 3  (OUTPUT) -> N2 blower solenoid
 *   SHT40 SDA -> A4, SHT40 SCL -> A5, VIN -> 3.3V/5V (check breakout), GND -> GND
 *
 * Serial protocol (single ASCII byte in, one line reply out):
 *   '1' -> blower ON            reply: "OK\n"
 *   '0' -> blower OFF           reply: "OK\n"
 *   'H' -> tester_output HIGH   reply: "OK\n"
 *   'L' -> tester_output LOW    reply: "OK\n"
 *   'P' -> poll tester_input    reply: "1\n" or "0\n"
 *   'S' -> read SHT40           reply: "<temp_C>,<humidity_%>\n" or "ERR,<reason>\n"
 */

#include <Wire.h>

const uint8_t PIN_TESTER_OUTPUT = 12;
const uint8_t PIN_TESTER_INPUT = 9;
const uint8_t PIN_BLOWER = 3;

const uint8_t SHT40_ADDR = 0x44;
const uint8_t CMD_MEASURE_HIGH_PRECISION = 0xFD;

uint8_t crc8(const uint8_t *data, int len) {
  uint8_t crc = 0xFF;
  for (int i = 0; i < len; i++) {
    crc ^= data[i];
    for (int b = 0; b < 8; b++) {
      if (crc & 0x80) crc = (crc << 1) ^ 0x31;
      else crc <<= 1;
    }
  }
  return crc;
}

// returns true on success, fills tempC / humidity
bool readSHT40(float &tempC, float &humidity) {
  Wire.beginTransmission(SHT40_ADDR);
  Wire.write(CMD_MEASURE_HIGH_PRECISION);
  if (Wire.endTransmission() != 0) {
    return false; // sensor didn't ack
  }

  delay(10); // datasheet: high precision measurement takes ~8.3ms max

  uint8_t bytesReceived = Wire.requestFrom((int)SHT40_ADDR, 6);
  if (bytesReceived != 6) {
    return false;
  }

  uint8_t buf[6];
  for (int i = 0; i < 6; i++) buf[i] = Wire.read();

  // verify CRCs
  if (crc8(buf, 2) != buf[2]) return false;      // temp CRC
  if (crc8(buf + 3, 2) != buf[5]) return false;  // humidity CRC

  uint16_t rawT = (buf[0] << 8) | buf[1];
  uint16_t rawRH = (buf[3] << 8) | buf[4];

  tempC = -45.0 + 175.0 * ((float)rawT / 65535.0);
  humidity = -6.0 + 125.0 * ((float)rawRH / 65535.0);
  if (humidity < 0) humidity = 0;
  if (humidity > 100) humidity = 100;

  return true;
}

void setup() {
  Serial.begin(115200);
  Wire.begin();

  pinMode(PIN_TESTER_OUTPUT, OUTPUT);
  pinMode(PIN_TESTER_INPUT, INPUT);
  pinMode(PIN_BLOWER, OUTPUT);

  digitalWrite(PIN_TESTER_OUTPUT, HIGH); // match original default: output high
  digitalWrite(PIN_BLOWER, LOW);
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();

    switch (cmd) {
      case '1':
        digitalWrite(PIN_BLOWER, HIGH);
        Serial.println("OK");
        break;

      case '0':
        digitalWrite(PIN_BLOWER, LOW);
        Serial.println("OK");
        break;

      case 'H':
        digitalWrite(PIN_TESTER_OUTPUT, HIGH);
        Serial.println("OK");
        break;

      case 'L':
        digitalWrite(PIN_TESTER_OUTPUT, LOW);
        Serial.println("OK");
        break;

      case 'P':
        Serial.println(digitalRead(PIN_TESTER_INPUT) == HIGH ? "1" : "0");
        break;

      case 'S': {
        float t, h;
        if (readSHT40(t, h)) {
          Serial.print(t, 2);
          Serial.print(",");
          Serial.println(h, 2);
        } else {
          Serial.println("ERR,SHT40 read failed");
        }
        break;
      }

      default:
        // ignore unknown/whitespace bytes (e.g. stray newlines)
        break;
    }
  }
}
