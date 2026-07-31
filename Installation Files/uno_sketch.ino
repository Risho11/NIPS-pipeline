/*
 * Last updated 7/31/26 
 * Ethan Mao
 *
 * Flash this ONCE from any PC with the Arduino IDE. After flashing,
 * the Arduino needs no further IDE/PC interaction - move it to the OT-2
 * and talk to it purely over serial (pyserial) from Python.
 *
 *
 * Wiring:
 *   Digital pin 12 (OUTPUT) -> compression tester trigger
 *   Digital pin 9  (INPUT)  -> compression tester status
 *   Digital pin 3  (OUTPUT) -> N2 coupon blower solenoid
 *   Digital pin 5  (OUTPUT) -> N2 pipette blower solenoid
 *   SHT40 SDA -> A4, SHT40 SCL -> A5, VIN -> 3.3V/5V (check breakout), GND ->
 * GND
 *
 * Serial protocol (single ASCII byte in, one line reply out):
 *   '1' -> coupon blower ON     reply: "OK\n"
 *   '0' -> coupon blower OFF    reply: "OK\n"
 *   'O' -> pipette blower ON    reply: "OK\n"
 *   'C' -> pipette blower OFF   reply: "OK\n"
 *   'H' -> tester_output HIGH   reply: "OK\n"
 *   'L' -> tester_output LOW    reply: "OK\n"
 *   'P' -> poll tester_input    reply: "1\n" or "0\n"
 *   'S' -> read SHT40           reply: "<temp_C>,<humidity_%>\n" or
 *                                      "ERR,<reason>\n"
 */

#include <Wire.h>

const uint8_t PIN_TESTER_OUTPUT = 12;
const uint8_t PIN_TESTER_INPUT = 9;
const uint8_t PIN_BLOWER_COUPON = 3;
const uint8_t PIN_BLOWER_PIPETTE = 5;

const uint8_t SHT40_ADDR = 0x44;
const uint8_t SHT31_ADDR = 0x45;
const uint8_t CMD_MEASURE_HIGH_PRECISION = 0xFD;
const uint8_t CMD_SHT31_MEASURE_HIGH_REP[2] = {0x2C, 0x06}; // SHT31 single-shot, high repeatability, clock stretching enabled

uint8_t crc8(const uint8_t* data, int len) {
  uint8_t crc = 0xFF;
  for (int i = 0; i < len; i++) {
    crc ^= data[i];
    for (int b = 0; b < 8; b++) {
      if (crc & 0x80)
        crc = (crc << 1) ^ 0x31;
      else
        crc <<= 1;
    }
  }
  return crc;
}

// returns true on success, fills tempC / humidity
bool readSHT40(float& tempC, float& humidity) {
  Wire.beginTransmission(SHT40_ADDR);
  Wire.write(CMD_MEASURE_HIGH_PRECISION);
  if (Wire.endTransmission() != 0) {
    return false;  // sensor didn't ack
  }

  delay(10);  // datasheet: high precision measurement takes ~8.3ms max

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

// returns true on success, fills tempC / humidity
// SHT31 uses a 2-byte measurement command (unlike SHT40's 1-byte command),
// but shares the same 6-byte reply layout and CRC8 (poly 0x31) as SHT40,
// so the existing crc8() helper is reused here.
bool readSHT31(float& tempC, float& humidity) {
  Wire.beginTransmission(SHT31_ADDR);
  Wire.write(CMD_SHT31_MEASURE_HIGH_REP[0]);
  Wire.write(CMD_SHT31_MEASURE_HIGH_REP[1]);
  if (Wire.endTransmission() != 0) {
    return false;  // sensor didn't ack
  }

  delay(15);  // datasheet: high repeatability measurement takes ~15ms max

  uint8_t bytesReceived = Wire.requestFrom((int)SHT31_ADDR, 6);
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

  // SHT31 conversion formulas (differ slightly from SHT40's humidity formula)
  tempC = -45.0 + 175.0 * ((float)rawT / 65535.0);
  humidity = 100.0 * ((float)rawRH / 65535.0);
  if (humidity < 0) humidity = 0;
  if (humidity > 100) humidity = 100;

  return true;
}

void setup() {
  Serial.begin(115200);
  Wire.begin();

  pinMode(PIN_TESTER_OUTPUT, OUTPUT);
  pinMode(PIN_TESTER_INPUT, INPUT);
  pinMode(PIN_BLOWER_COUPON, OUTPUT);
  pinMode(PIN_BLOWER_PIPETTE, OUTPUT);

  digitalWrite(PIN_TESTER_OUTPUT, HIGH);  // match original default: output high
  digitalWrite(PIN_BLOWER_COUPON, LOW);
  digitalWrite(PIN_BLOWER_PIPETTE, LOW);
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();

    switch (cmd) {
      // 1st solenoid
      case '1':
        digitalWrite(PIN_BLOWER_COUPON, HIGH);
        Serial.println("OK");
        break;

      case '0':
        digitalWrite(PIN_BLOWER_COUPON, LOW);
        Serial.println("OK");
        break;

      // 2nd solenoid
      case 'O':
        digitalWrite(PIN_BLOWER_PIPETTE, HIGH);
        Serial.println("OK");
        break;

      case 'C':
        digitalWrite(PIN_BLOWER_PIPETTE, LOW);
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

      // SHT40
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

      // SHT31
      case 'T': {
        float t, h;
        if (readSHT31(t, h)) {
          Serial.print(t, 2);
          Serial.print(",");
          Serial.println(h, 2);
        } else {
          Serial.println("ERR,SHT31 read failed");
        }
        break;
      }

      default:
        // ignore unknown/whitespace bytes (e.g. stray newlines)
        break;
    }
  }
}
