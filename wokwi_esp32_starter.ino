// Wokwi ESP32 starter: simulated two-zone temperature inputs and two PWM fan outputs.
// For first test, use potentiometers as analog temperature controls (or replace with supported sensors).
// GPIO 34 = Zone 1 analog input, GPIO 35 = Zone 2 analog input
// GPIO 18 = Fan 1 PWM output, GPIO 19 = Fan 2 PWM output
const int TEMP1_PIN = 34;
const int TEMP2_PIN = 35;
const int FAN1_PIN = 18;
const int FAN2_PIN = 19;
const int PWM_FREQ = 25000;
const int PWM_RES = 8;
const int FAN1_CHANNEL = 0;
const int FAN2_CHANNEL = 1;

float readDemoTemp(int pin) {
  int raw = analogRead(pin);
  // Convert 0..4095 to a demonstration range of 20..50 C.
  return 20.0 + (raw / 4095.0) * 30.0;
}

int fanForTemp(float t) {
  if (t < 30.0) return 70;   // demo baseline airflow
  if (t < 38.0) return 150;  // medium
  return 230;                // high
}

void setup() {
  Serial.begin(115200);
  ledcSetup(FAN1_CHANNEL, PWM_FREQ, PWM_RES);
  ledcSetup(FAN2_CHANNEL, PWM_FREQ, PWM_RES);
  ledcAttachPin(FAN1_PIN, FAN1_CHANNEL);
  ledcAttachPin(FAN2_PIN, FAN2_CHANNEL);
}

void loop() {
  float t1 = readDemoTemp(TEMP1_PIN);
  float t2 = readDemoTemp(TEMP2_PIN);
  int pwm1 = fanForTemp(t1);
  int pwm2 = fanForTemp(t2);
  ledcWrite(FAN1_CHANNEL, pwm1);
  ledcWrite(FAN2_CHANNEL, pwm2);

  Serial.printf("Zone1=%.1f C Fan1=%d%% | Zone2=%.1f C Fan2=%d%%\\n",
                t1, (pwm1 * 100) / 255, t2, (pwm2 * 100) / 255);
  delay(1000);
}
