#pragma once

#include <Arduino.h>

class PWMEngine
{
public:
  explicit PWMEngine(uint8_t pin)
    : _pin(pin)
  {
  }

  void begin()
  {
    pinMode(_pin, OUTPUT);
    digitalWrite(_pin, LOW);

    _enabled = false;
    _output_state = false;
    _last_change = millis();

    Serial.println("[PWM] PWMEngine ready");
  }

  void enable(bool en)
  {
    if (!en)
    {
      _enabled = false;
      _output_state = false;
      digitalWrite(_pin, LOW);
      return;
    }

    if (!_enabled)
    {
      _enabled = true;
      _last_change = millis();
      _output_state = false;
      digitalWrite(_pin, LOW);
    }
  }

  void setPeriod(uint32_t period_ms)
  {
    _period_ms = max((uint32_t)100, period_ms);
  }

  void setDuty(uint8_t duty_percent)
  {
    if (duty_percent > 100)
      duty_percent = 100;

    _duty_percent = duty_percent;
  }

  uint32_t getPeriod() const
  {
    return _period_ms;
  }

  uint8_t getDuty() const
  {
    return _duty_percent;
  }

  bool isEnabled() const
  {
    return _enabled;
  }

  bool outputState() const
  {
    return _output_state;
  }

  void update()
  {
    if (!_enabled)
    {
      if (_output_state)
      {
        _output_state = false;
        digitalWrite(_pin, LOW);
      }
      return;
    }

    if (_duty_percent == 0)
    {
      if (_output_state)
      {
        _output_state = false;
        digitalWrite(_pin, LOW);
      }
      return;
    }

    if (_duty_percent >= 100)
    {
      if (!_output_state)
      {
        _output_state = true;
        digitalWrite(_pin, HIGH);
      }
      return;
    }

    uint32_t now = millis();

    uint32_t on_time  = (_period_ms * _duty_percent) / 100UL;
    uint32_t off_time = _period_ms - on_time;

    if (_output_state)
    {
      if ((uint32_t)(now - _last_change) >= on_time)
      {
        _output_state = false;
        _last_change = now;
        digitalWrite(_pin, LOW);
      }
    }
    else
    {
      if ((uint32_t)(now - _last_change) >= off_time)
      {
        _output_state = true;
        _last_change = now;
        digitalWrite(_pin, HIGH);
      }
    }
  }

private:
  uint8_t _pin;

  bool _enabled = false;
  bool _output_state = false;

  uint8_t _duty_percent = 0;
  uint32_t _period_ms = 5000;
  uint32_t _last_change = 0;
};