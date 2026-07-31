#pragma once

#include <Arduino.h>
#include <math.h>

class PIDEngine
{
public:
  void begin(uint8_t pin_open, uint8_t pin_close)
  {
    _pin_open  = pin_open;
    _pin_close = pin_close;

    pinMode(_pin_open, OUTPUT);
    pinMode(_pin_close, OUTPUT);

    digitalWrite(_pin_open, LOW);
    digitalWrite(_pin_close, LOW);

    reset();

    Serial.println("[PID] PIDEngine relay-safe mode ready");
  }

  void begin() {}

  void reset()
  {
    _state = IDLE;
    _last_enable = false;

    _position = 0.0f;
    _moving = false;
    _direction = 0;

    _timer = 0;
    _interval = 0;
    _move_start = 0;
    _dbg_timer = 0;

    _pending_direction = 0;
    _last_stop_time = 0;
  }

  // ---------------- CONFIG ----------------

  void setTiming(uint16_t t_full_sec)
  {
    _t_full = max((uint16_t)1, t_full_sec);
  }

  void setMoveTime(uint16_t t_move_sec)
  {
    _t_move = max((uint16_t)1, t_move_sec);
  }

  void setDeadband(float db)
  {
    _deadband = db;
  }

  void setHotSoakTime(uint16_t soak_sec)
  {
    _t_soak_hot = soak_sec;
  }

  void setColdSoakTime(uint16_t soak_sec)
  {
    _t_soak_cold = soak_sec;
  }

  void setFastSettleTime(uint16_t settle_ms)
  {
    _settle_fast_ms = max((uint16_t)500, settle_ms);
  }

  void setRegSettleTime(uint16_t settle_ms)
  {
    _settle_reg_ms = max((uint16_t)500, settle_ms);
  }

  void setCentering(bool enable_centering)
  {
    _center_after_flush = enable_centering;
  }

  void setDirectionPause(uint16_t pause_ms)
  {
    _direction_pause_ms = max((uint16_t)100, pause_ms);
  }

  // ---------------- MAIN ----------------

  void process(float t_set, float t_mix, bool enable_pid)
  {
    uint32_t now = millis();

    updatePosition(now);

    float error = t_set - t_mix;

    if (now - _dbg_timer >= 1000)
    {
      _dbg_timer = now;

      Serial.print("[PID] t=");
      Serial.print(now / 1000.0f, 1);
      Serial.print("s");

      Serial.print(" EN=");
      Serial.print(enable_pid ? 1 : 0);

      Serial.print(" STATE=");
      Serial.print(stateName(_state));

      Serial.print(" POS=");
      Serial.print(_position, 1);

      Serial.print(" ERR=");
      Serial.print(error, 2);

      Serial.print(" Tset=");
      Serial.print(t_set, 1);

      Serial.print(" Tmix=");
      Serial.print(t_mix, 1);

      Serial.print(" MOV=");
      Serial.print(_moving ? 1 : 0);

      Serial.print(" DIR=");
      Serial.print(_direction);

      Serial.print(" PDIR=");
      Serial.print(_pending_direction);

      Serial.print(" INT=");
      Serial.print(_interval);

      Serial.print(" HOTSOAK=");
      Serial.print(_t_soak_hot);

      Serial.print(" COLDSOAK=");
      Serial.print(_t_soak_cold);

      Serial.print(" FASTSET=");
      Serial.print(_settle_fast_ms);

      Serial.print(" REGSET=");
      Serial.print(_settle_reg_ms);

      Serial.print(" DIRPAUSE=");
      Serial.println(_direction_pause_ms);
    }

    if (enable_pid && !_last_enable)
    {
      Serial.println("[PID] START -> INIT_HOT");

      _state = INIT_HOT;
      closeValve(now);
      _timer = now;
      _interval = _t_full * 1000UL;
    }

    _last_enable = enable_pid;

    if (!enable_pid)
    {
      stopValve(now);
      _state = IDLE;
      return;
    }

    if ((uint32_t)(now - _timer) < _interval)
      return;

    _timer = now;

    switch (_state)
    {
      case INIT_HOT:
      {
        stopValve(now);
        _position = 0.0f;

        if (_t_soak_hot > 0)
        {
          _state = SOAK_HOT;
          _interval = _t_soak_hot * 1000UL;
          Serial.println("[PID] INIT_HOT -> SOAK_HOT");
        }
        else
        {
          _state = INIT_COLD;
          openValve(now);
          _interval = _t_full * 1000UL;
          Serial.println("[PID] INIT_HOT -> INIT_COLD");
        }
        break;
      }

      case SOAK_HOT:
      {
        stopValve(now);
        _state = INIT_COLD;
        openValve(now);
        _interval = _t_full * 1000UL;
        Serial.println("[PID] SOAK_HOT -> INIT_COLD");
        break;
      }

      case INIT_COLD:
      {
        stopValve(now);
        _position = 100.0f;

        if (_t_soak_cold > 0)
        {
          _state = SOAK_COLD;
          _interval = _t_soak_cold * 1000UL;
          Serial.println("[PID] INIT_COLD -> SOAK_COLD");
        }
        else if (_center_after_flush)
        {
          _state = CENTER_TO_MID;
          closeValve(now);
          _interval = (_t_full * 1000UL) / 2;
          Serial.println("[PID] INIT_COLD -> CENTER_TO_MID");
        }
        else
        {
          _state = FAST_EVAL;
          _interval = 200;
          Serial.println("[PID] INIT_COLD -> FAST_EVAL");
        }
        break;
      }

      case SOAK_COLD:
      {
        stopValve(now);

        if (_center_after_flush)
        {
          _state = CENTER_TO_MID;
          closeValve(now);
          _interval = (_t_full * 1000UL) / 2;
          Serial.println("[PID] SOAK_COLD -> CENTER_TO_MID");
        }
        else
        {
          _state = FAST_EVAL;
          _interval = 200;
          Serial.println("[PID] SOAK_COLD -> FAST_EVAL");
        }
        break;
      }

      case CENTER_TO_MID:
      {
        stopValve(now);
        _position = 50.0f;
        _state = FAST_EVAL;
        _interval = _settle_fast_ms;
        Serial.println("[PID] CENTER_TO_MID -> FAST_EVAL");
        break;
      }

      case FAST_EVAL:
      {
        stopValve(now);

        if (fabs(error) <= _deadband)
        {
          _state = REG_EVAL;
          _interval = _settle_reg_ms;
          Serial.println("[PID] FAST_EVAL -> REG_EVAL");
        }
        else
        {
          _pending_direction = directionFromError(error);
          _state = DIR_PAUSE;
          _interval = _direction_pause_ms;

          Serial.print("[PID] FAST_EVAL -> DIR_PAUSE dir=");
          Serial.println(_pending_direction);
        }
        break;
      }

      case REG_EVAL:
      {
        stopValve(now);

        if (fabs(error) <= _deadband)
        {
          _interval = _settle_reg_ms;
        }
        else
        {
          _pending_direction = directionFromError(error);
          _state = DIR_PAUSE;
          _interval = _direction_pause_ms;

          Serial.print("[PID] REG_EVAL -> DIR_PAUSE dir=");
          Serial.println(_pending_direction);
        }
        break;
      }

      case DIR_PAUSE:
      {
        stopValve(now);

        if (_pending_direction == 0)
        {
          _state = FAST_EVAL;
          _interval = 100;
          break;
        }

        if (_pending_direction == +1)
          openValve(now);
        else
          closeValve(now);

        if (fabs(error) <= 2.0f)
        {
          _state = REG_PULSE;
          _interval = computePulseMsReg(error);

          Serial.print("[PID] DIR_PAUSE -> REG_PULSE ms=");
          Serial.println(_interval);
        }
        else
        {
          _state = FAST_PULSE;
          _interval = computePulseMs(error);

          Serial.print("[PID] DIR_PAUSE -> FAST_PULSE ms=");
          Serial.println(_interval);
        }

        _pending_direction = 0;
        break;
      }

      case FAST_PULSE:
      {
        stopValve(now);
        _state = FAST_SETTLE;
        _interval = _settle_fast_ms;
        Serial.println("[PID] FAST_PULSE -> FAST_SETTLE");
        break;
      }

      case FAST_SETTLE:
      {
        _state = FAST_EVAL;
        _interval = 100;
        Serial.println("[PID] FAST_SETTLE -> FAST_EVAL");
        break;
      }

      case REG_PULSE:
      {
        stopValve(now);
        _state = REG_SETTLE;
        _interval = _settle_reg_ms;
        Serial.println("[PID] REG_PULSE -> REG_SETTLE");
        break;
      }

      case REG_SETTLE:
      {
        _state = REG_EVAL;
        _interval = 100;
        Serial.println("[PID] REG_SETTLE -> REG_EVAL");
        break;
      }

      default:
        break;
    }
  }

  uint16_t getPosition() const
  {
    return (uint16_t)_position;
  }

private:
  enum State
  {
    IDLE,
    INIT_HOT,
    SOAK_HOT,
    INIT_COLD,
    SOAK_COLD,
    CENTER_TO_MID,
    FAST_EVAL,
    DIR_PAUSE,
    FAST_PULSE,
    FAST_SETTLE,
    REG_EVAL,
    REG_PULSE,
    REG_SETTLE
  };

  State _state = IDLE;

  uint8_t _pin_open = 0;
  uint8_t _pin_close = 0;

  uint32_t _timer = 0;
  uint32_t _interval = 0;

  uint16_t _t_full = 120;
  uint16_t _t_move = 10;
  uint16_t _t_soak_hot = 20;
  uint16_t _t_soak_cold = 20;

  uint16_t _settle_fast_ms = 4000;
  uint16_t _settle_reg_ms  = 6000;
  uint16_t _direction_pause_ms = 500;

  float _deadband = 0.5f;
  bool _last_enable = false;
  bool _center_after_flush = true;

  float _position = 0.0f;

  uint32_t _move_start = 0;
  uint32_t _last_stop_time = 0;
  int _direction = 0;
  int _pending_direction = 0;
  bool _moving = false;

  uint32_t _dbg_timer = 0;

  const char* stateName(State s) const
  {
    switch (s)
    {
      case IDLE:          return "IDLE";
      case INIT_HOT:      return "INIT_HOT";
      case SOAK_HOT:      return "SOAK_HOT";
      case INIT_COLD:     return "INIT_COLD";
      case SOAK_COLD:     return "SOAK_COLD";
      case CENTER_TO_MID: return "CENTER";
      case FAST_EVAL:     return "FAST_EVAL";
      case DIR_PAUSE:     return "DIR_PAUSE";
      case FAST_PULSE:    return "FAST_PULSE";
      case FAST_SETTLE:   return "FAST_SETTLE";
      case REG_EVAL:      return "REG_EVAL";
      case REG_PULSE:     return "REG_PULSE";
      case REG_SETTLE:    return "REG_SETTLE";
      default:            return "?";
    }
  }

  int directionFromError(float error) const
  {
    if (error > 0) return -1; // viac horúcej
    if (error < 0) return +1; // viac studenej
    return 0;
  }

  uint32_t computePulseMs(float error) const
  {
    float ae = fabs(error);

    if (ae >= 8.0f) return 2500;
    if (ae >= 5.0f) return 2000;
    if (ae >= 3.0f) return 1500;
    if (ae >= 1.5f) return 1200;
    if (ae >= 0.7f) return 1000;
    return 800;
  }

  uint32_t computePulseMsReg(float error) const
  {
    float ae = fabs(error);

    if (ae >= 3.0f) return 1500;
    if (ae >= 1.5f) return 1200;
    if (ae >= 0.8f) return 1000;
    return 800;
  }

  void updatePosition(uint32_t now)
  {
    if (!_moving) return;

    uint32_t dt = now - _move_start;
    float delta = (dt / (_t_full * 1000.0f)) * 100.0f;

    _position += delta * _direction;
    _position = constrain(_position, 0.0f, 100.0f);

    _move_start = now;
  }

  void openValve(uint32_t now)
  {
    if (_moving && _direction == +1)
      return;

    stopValve(now);

    digitalWrite(_pin_open, HIGH);
    digitalWrite(_pin_close, LOW);

    startMove(+1, now);
  }

  void closeValve(uint32_t now)
  {
    if (_moving && _direction == -1)
      return;

    stopValve(now);

    digitalWrite(_pin_open, LOW);
    digitalWrite(_pin_close, HIGH);

    startMove(-1, now);
  }

  void stopValve(uint32_t now)
  {
    updatePosition(now);

    digitalWrite(_pin_open, LOW);
    digitalWrite(_pin_close, LOW);

    _moving = false;
    _direction = 0;
    _last_stop_time = now;
  }

  void startMove(int dir, uint32_t now)
  {
    _move_start = now;
    _moving = true;
    _direction = dir;
  }
};