#include <Arduino.h>
#include <ArduinoJson.h>
#include <Wire.h>

#include "motion_safety.hpp"
#include "protocol.hpp"

namespace {
constexpr int kGatePin = 26;
constexpr int kOePin = 25;
constexpr int kPiRxPin = 16;
constexpr int kPiTxPin = 17;
constexpr uint8_t kImuAddress = 0x68;
constexpr std::size_t kMaxLineBytes = microduck::kMaxLineBytes;
constexpr uint32_t kImuPeriodMs = 20;
constexpr uint32_t kImuStaleMs = 100;

HardwareSerial pi(2);
microduck::MotionSafety safety;
char line[kMaxLineBytes + 1]{};
std::size_t line_size = 0;
bool overflow = false;
bool imu_detected = false;
bool imu_sample_valid = false;
uint32_t imu_sample_ms = 0;
uint32_t imu_attempt_ms = 0;
int16_t accel[3]{};
int16_t gyro[3]{};

// Output interlocks are unconditional in this scaffold. No motor/PCA9685 writes
// exist, and no UART command can enable power or PWM.
void inhibit_outputs() {
    digitalWrite(kGatePin, LOW);   // External motor-power enable: active high.
    digitalWrite(kOePin, HIGH);   // PCA9685 OE: active low; high disables outputs.
}

bool read_register(uint8_t reg, uint8_t* bytes, std::size_t count) {
    Wire.beginTransmission(kImuAddress);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) return false;
    if (Wire.requestFrom(kImuAddress, static_cast<uint8_t>(count)) != count) return false;
    for (std::size_t i = 0; i < count; ++i) bytes[i] = Wire.read();
    return true;
}

bool initialize_imu() {
    uint8_t identity = 0;
    if (!read_register(0x75, &identity, 1) || identity != 0x68) return false;
    // Wake only the sensor and select explicit +/-2 g and +/-250 deg/s scales.
    for (uint8_t reg : {uint8_t{0x6B}, uint8_t{0x1B}, uint8_t{0x1C}}) {
        Wire.beginTransmission(kImuAddress);
        Wire.write(reg);
        Wire.write(0x00);
        if (Wire.endTransmission() != 0) return false;
    }
    return true;
}

int16_t signed_word(const uint8_t* data) {
    return static_cast<int16_t>((static_cast<uint16_t>(data[0]) << 8) | data[1]);
}

void sample_imu(uint32_t now) {
    if (static_cast<uint32_t>(now - imu_attempt_ms) < kImuPeriodMs) return;
    imu_attempt_ms = now;
    imu_sample_valid = false;
    if (!imu_detected) return;
    uint8_t bytes[14];
    if (!read_register(0x3B, bytes, sizeof(bytes))) return;
    for (int i = 0; i < 3; ++i) {
        accel[i] = signed_word(bytes + 2 * i);
        gyro[i] = signed_word(bytes + 8 + 2 * i);
    }
    imu_sample_ms = now;
    imu_sample_valid = true;
}

bool imu_valid(uint32_t now) {
    return imu_sample_valid && static_cast<uint32_t>(now - imu_sample_ms) <= kImuStaleMs;
}

void respond(uint32_t seq, const char* type, const char* error = nullptr) {
    JsonDocument doc;
    const auto now = millis();
    doc["v"] = 1;
    doc["seq"] = seq;
    doc["type"] = type;
    doc["state"] = microduck::state_name(safety.state());
    doc["outputs_enabled"] = false;
    if (error) doc["error"] = error;
    if (!strcmp(type, "status")) {
        doc["firmware_mode"] = "no_motor_backend";
        doc["calibration_valid"] = false;
        doc["physical_estop_verified"] = false;
        doc["imu"]["valid"] = imu_valid(now);
        doc["imu"]["sample_ms"] = imu_sample_ms;
        doc["imu"]["calibrated"] = false;
        doc["imu"]["filtered"] = false;
        if (imu_valid(now)) {
            for (int i = 0; i < 3; ++i) {
                doc["imu"]["accel_g"][i] = accel[i] / 16384.0;
                doc["imu"]["gyro_dps"][i] = gyro[i] / 131.0;
            }
        }
        if (safety.state() == microduck::State::Fault || safety.state() == microduck::State::Estop)
            doc["fault_reason"] = safety.fault_reason();
    }
    serializeJson(doc, pi);
    pi.write('\n');
}

void handle_line() {
    microduck::Request request;
    const auto parse_error = microduck::decode_request(line, line_size, request);
    const uint32_t seq = request.seq;
    if (parse_error) { respond(seq, "error", parse_error); return; }
    const auto now = millis();
    safety.tick(now);
    if (request.command == microduck::Command::Status) { respond(seq, "status"); return; }
    if (request.command == microduck::Command::Estop) {
        safety.estop(); inhibit_outputs(); respond(seq, "ack"); return;
    }
    if (request.command == microduck::Command::Disarm) {
        safety.disarm(); inhibit_outputs(); respond(seq, "ack"); return;
    }
    if (request.command == microduck::Command::Arm) {
        // Neither JSON flags nor a host assertion can supply calibration or
        // authorization; this firmware has no commissioning/output backend.
        respond(seq, "error", "motor_backend_disabled"); return;
    }
    if (request.command == microduck::Command::Target) {
        const auto error = safety.target(request.positions, now);
        respond(seq, error ? "error" : "ack", error);
        return;
    }
    respond(seq, "error", "unknown_command");
}
}  // namespace

void setup() {
    // External gate pulldown / OE pullup keep outputs disabled before setup.
    digitalWrite(kGatePin, LOW);
    digitalWrite(kOePin, HIGH);
    pinMode(kGatePin, OUTPUT);
    pinMode(kOePin, OUTPUT);
    inhibit_outputs();
    Serial.begin(115200);
    pi.begin(115200, SERIAL_8N1, kPiRxPin, kPiTxPin);
    Wire.begin(21, 22);
    Wire.setTimeOut(10);
    imu_detected = initialize_imu();
    Serial.println("Microduck scaffold: motor backend absent; outputs inhibited.");
}

void loop() {
    inhibit_outputs();
    const auto now = millis();
    sample_imu(now);
    microduck::SafetyInputs inputs;
    inputs.imu_valid = imu_valid(now);
    // All commissioning and physical authorization prerequisites remain false.
    safety.update_inputs(inputs);
    safety.tick(now);
    // Bound work per loop so malformed/continuous UART input cannot starve safety.
    for (int processed = 0; processed < 128 && pi.available(); ++processed) {
        const auto ch = static_cast<char>(pi.read());
        if (ch == '\n') {
            if (overflow) respond(0, "error", "line_too_long");
            else if (line_size) handle_line();
            line_size = 0;
            overflow = false;
        } else if (!overflow) {
            if (line_size >= kMaxLineBytes) overflow = true;
            else line[line_size++] = ch;
        }
    }
    delay(1);
}
