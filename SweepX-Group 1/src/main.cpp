#include <HardwareSerial.h>
#include <WiFi.h>
#include <esp_now.h>

HardwareSerial tof1(1);
HardwareSerial tof2(2);

#define RXD1 16
#define TXD1 17
#define RXD2 26
#define TXD2 25

#define FRAME_LENGTH 16
#define REPORT_INTERVAL 200

uint8_t frame1[FRAME_LENGTH];
uint8_t frame2[FRAME_LENGTH];

float sum1 = 0, sum2 = 0;
int count1 = 0, count2 = 0;

float remote3 = 0;
float remote4 = 0;

unsigned long lastReport = 0;

typedef struct {
  float sensor3;
  float sensor4;
} SensorPacket;

void OnDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
  SensorPacket incoming;
  memcpy(&incoming, incomingData, sizeof(incoming));

  remote3 = incoming.sensor3;
  remote4 = incoming.sensor4;
}

void setup() {
  Serial.begin(115200);

  tof1.begin(921600, SERIAL_8N1, RXD1, TXD1);
  tof2.begin(921600, SERIAL_8N1, RXD2, TXD2);

  WiFi.mode(WIFI_STA);
  esp_now_init();
  esp_now_register_recv_cb(OnDataRecv);
}

void readSensor(HardwareSerial &tof, uint8_t *frame, float &sum, int &count) {
  if (tof.available() >= FRAME_LENGTH) {
    if (tof.read() == 0x57) {
      frame[0] = 0x57;
      tof.readBytes(&frame[1], FRAME_LENGTH - 1);

      if (frame[1] == 0x00) {
        uint16_t distance_mm = frame[8] | (frame[9] << 8);
        uint8_t status = frame[10];

        if (status == 0x00) {
          float distance_cm = distance_mm / 10.0;
          if (distance_cm > 2 && distance_cm < 800) {
            sum += distance_cm;
            count++;
          }
        }
      }
    }
  }
}

void loop() {

  readSensor(tof1, frame1, sum1, count1);
  readSensor(tof2, frame2, sum2, count2);

  if (millis() - lastReport >= REPORT_INTERVAL) {

    float avg1 = (count1 > 0) ? sum1 / count1 : 0;
    float avg2 = (count2 > 0) ? sum2 / count2 : 0;

    Serial.println("------ ALL SENSORS ------");
    Serial.print("Sensor 1: "); Serial.println(avg1);
    Serial.print("Sensor 2: "); Serial.println(avg2);
    Serial.print("Sensor 3: "); Serial.println(remote3);
    Serial.print("Sensor 4: "); Serial.println(remote4);

    // Reset
    sum1 = sum2 = 0;
    count1 = count2 = 0;
    lastReport = millis();
  }
}
