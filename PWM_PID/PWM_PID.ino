/*
  OPTA – Dual Controller (FINAL FIX)
*/

#include <Arduino.h>
#include <ArduinoRS485.h>
#include <ArduinoModbus.h>

#include "PWM_engine.h"
#include "PID_engine.h"

#define SLAVE_ID 1

// ---------------- RS485 ----------------

constexpr auto baudrate = 9600;
constexpr auto bitduration = 1.0f / baudrate;
constexpr auto wordlen = 10.0f;

constexpr auto preDelayBR  = bitduration * 9.6f * wordlen * 4.0f * 1e6;
constexpr auto postDelayBR = bitduration * 9.6f * wordlen * 3.0f * 1e6;


// ---------------- ANALOG INPUTS ----------------

#define AI_T_HOT   A0
#define AI_T_COLD  A1
#define AI_T_MIX   A2


// ---------------- OUTPUTS ----------------
//
// Overené zapojenie:
// D2 = OPEN  = viac studenej = POS rastie k 100
// D1 = CLOSE = viac horúcej  = POS klesá k 0

#define DO_PWM         D0
#define DO_VALVE_OPEN  D2
#define DO_VALVE_CLOSE D1


// ---------------- COILS ----------------

#define COIL_ENABLE_PWM  0
#define COIL_ENABLE_PID  1


// ---------------- HOLDING REGISTERS ----------------

#define REG_PWM_PERIOD 0
#define REG_PWM_DUTY   1
#define REG_T_SET      2
#define REG_T_FULL     3
#define REG_T_MOVE     4


// ---------------- INPUT REGISTERS ----------------

#define REG_T_HOT      0
#define REG_T_COLD     1
#define REG_T_MIX      2
#define REG_VALVE_POS  3
#define REG_STATUS     4


// ---------------- GLOBAL VARIABLES ----------------

uint16_t pwm_period = 5000;
uint16_t pwm_duty   = 0;

uint16_t t_set  = 400;   // 40.0 °C
uint16_t t_full = 120;   // s
uint16_t t_move = 10;    // s

int16_t t_hot  = 0;
int16_t t_cold = 0;
int16_t t_mix  = 0;

uint16_t valve_position = 0;
uint16_t status_flags   = 0;


// ---------------- CONTROLLERS ----------------

PWMEngine pwm(DO_PWM);
PIDEngine valve;


// ---------------- FILTER ----------------

float f_hot  = 0.0f;
float f_cold = 0.0f;
float f_mix  = 0.0f;

const float alpha = 0.1f;
bool temp_initialized = false;


// ------------------------------------------------
// Temperature read
// ------------------------------------------------

float readTemp(uint8_t pin)
{
  uint32_t sum = 0;

  for (int i = 0; i < 16; i++)
    sum += analogRead(pin);

  float raw = sum / 16.0f;

  // kalibrácia:
  // 1633 -> 17.4 °C
  // 2385 -> 48.7 °C
  return raw * 0.04162f - 50.0f;
}


// ------------------------------------------------
// EMA filter
// ------------------------------------------------

float filter(float prev, float in)
{
  return prev + alpha * (in - prev);
}


// ------------------------------------------------
// SETUP
// ------------------------------------------------

void setup()
{
  Serial.begin(115200);
  delay(2000);

  Serial.println("[MAIN] OPTA boot OK");

  analogReadResolution(12);

  RS485.setDelays(preDelayBR, postDelayBR);

  if (!ModbusRTUServer.begin(SLAVE_ID, baudrate, SERIAL_8N1))
  {
    Serial.println("[MAIN] ModbusRTUServer.begin FAILED");
    while (1);
  }

  ModbusRTUServer.configureHoldingRegisters(0x00, 10);
  ModbusRTUServer.configureInputRegisters(0x00, 10);
  ModbusRTUServer.configureCoils(0x00, 4);

  pwm.begin();

  valve.begin(DO_VALVE_OPEN, DO_VALVE_CLOSE);
  valve.setTiming(t_full);
  valve.setMoveTime(t_move);
  valve.setDeadband(0.5f);

  valve.setHotSoakTime(20);
  valve.setColdSoakTime(20);

  valve.setFastSettleTime(3000);
  valve.setRegSettleTime(4000);

  valve.setCentering(true);
  valve.reset();

  digitalWrite(DO_PWM, LOW);
  digitalWrite(DO_VALVE_OPEN, LOW);
  digitalWrite(DO_VALVE_CLOSE, LOW);

  Serial.println("[MAIN] Controller ready");
}


// ------------------------------------------------
// LOOP
// ------------------------------------------------

void loop()
{
  pwm.update();

  // ---------------- READ TEMPERATURES ----------------

  float Th = readTemp(AI_T_HOT);
  float Tc = readTemp(AI_T_COLD);
  float Tm = readTemp(AI_T_MIX);

  if (!temp_initialized)
  {
    f_hot = Th;
    f_cold = Tc;
    f_mix = Tm;
    temp_initialized = true;
  }
  else
  {
    f_hot  = filter(f_hot, Th);
    f_cold = filter(f_cold, Tc);
    f_mix  = filter(f_mix, Tm);
  }

  t_hot  = (int16_t)(f_hot * 10.0f);
  t_cold = (int16_t)(f_cold * 10.0f);
  t_mix  = (int16_t)(f_mix * 10.0f);

  // ---------------- MODBUS ----------------

  ModbusRTUServer.poll();

  pwm_period = ModbusRTUServer.holdingRegisterRead(REG_PWM_PERIOD);
  pwm_duty   = ModbusRTUServer.holdingRegisterRead(REG_PWM_DUTY);

  t_set  = ModbusRTUServer.holdingRegisterRead(REG_T_SET);
  t_full = ModbusRTUServer.holdingRegisterRead(REG_T_FULL);
  t_move = ModbusRTUServer.holdingRegisterRead(REG_T_MOVE);

  bool enable_pwm = ModbusRTUServer.coilRead(COIL_ENABLE_PWM);
  bool enable_pid = ModbusRTUServer.coilRead(COIL_ENABLE_PID);

  // ---------------- PWM ----------------

  pwm.setPeriod(pwm_period);

  if (enable_pwm)
  {
    pwm.enable(true);
    pwm.setDuty((uint8_t)pwm_duty);
  }
  else
  {
    pwm.setDuty(0);
    pwm.enable(false);
    digitalWrite(DO_PWM, LOW);
  }

  // ---------------- VALVE ----------------

  valve.setTiming(t_full);
  valve.setMoveTime(t_move);

  float Tset = t_set / 10.0f;
  float Tmix = t_mix / 10.0f;

  valve.process(Tset, Tmix, enable_pid);
  valve_position = valve.getPosition();

  // ---------------- STATUS ----------------

  status_flags = 0;
  if (enable_pwm) status_flags |= 1;
  if (enable_pid) status_flags |= 2;

  // ---------------- SEND STATE ----------------

  ModbusRTUServer.inputRegisterWrite(REG_T_HOT, t_hot);
  ModbusRTUServer.inputRegisterWrite(REG_T_COLD, t_cold);
  ModbusRTUServer.inputRegisterWrite(REG_T_MIX, t_mix);
  ModbusRTUServer.inputRegisterWrite(REG_VALVE_POS, valve_position);
  ModbusRTUServer.inputRegisterWrite(REG_STATUS, status_flags);

  // ---------------- DEBUG ----------------

  static uint32_t last = 0;
  uint32_t now = millis();

  if ((int32_t)(now - last) >= 1000)
  {
    last = now;

    Serial.print("[MAIN] t=");
    Serial.print(now / 1000.0f, 1);
    Serial.print("s");

    Serial.print(" ThRaw=");
    Serial.print(Th, 2);

    Serial.print(" TcRaw=");
    Serial.print(Tc, 2);

    Serial.print(" TmRaw=");
    Serial.print(Tm, 2);

    Serial.print(" Th=");
    Serial.print(t_hot / 10.0f, 1);

    Serial.print(" Tc=");
    Serial.print(t_cold / 10.0f, 1);

    Serial.print(" Tm=");
    Serial.print(t_mix / 10.0f, 1);

    Serial.print(" Tset=");
    Serial.print(Tset, 1);

    Serial.print(" PWMen=");
    Serial.print(enable_pwm ? 1 : 0);

    Serial.print(" PWM=");
    Serial.print(pwm_duty);

    Serial.print(" PIDen=");
    Serial.print(enable_pid ? 1 : 0);

    Serial.print(" POS=");
    Serial.print(valve_position);

    Serial.print(" ST=");
    Serial.println(status_flags);
  }
}