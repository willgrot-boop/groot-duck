#pragma once

#include <array>
#include <cmath>
#include <cstdint>

namespace microduck {

constexpr std::size_t kJointCount = 8;
constexpr std::uint32_t kWatchdogMs = 500;
constexpr std::array<const char*, kJointCount> kJointNames{{
    "left_hip_pitch", "left_knee", "left_ankle_pitch",
    "right_hip_pitch", "right_knee", "right_ankle_pitch", "head_pan", "head_tilt"}};

// Provisional software envelopes, NOT servo calibration or mechanically verified travel.
constexpr std::array<double, kJointCount> kMinDeg{{-35, 0, -30, -35, 0, -30, -60, -25}};
constexpr std::array<double, kJointCount> kMaxDeg{{35, 75, 30, 35, 75, 30, 60, 25}};
constexpr double kMaxSpeedDegS = 60.0;
using Positions = std::array<double, kJointCount>;

enum class State { Disarmed, Armed, Estop, Fault };

inline const char* state_name(State state) {
    switch (state) {
        case State::Disarmed: return "disarmed";
        case State::Armed: return "armed";
        case State::Estop: return "estop";
        case State::Fault: return "fault";
    }
    return "fault";
}

struct SafetyInputs {
    bool calibration_valid = false;
    bool bench_approved = false;
    bool imu_valid = false;
    bool physical_estop_clear = false;
    bool output_backend_ready = false;

    bool all_verified() const {
        return calibration_valid && bench_approved && imu_valid &&
               physical_estop_clear && output_backend_ready;
    }
};

// Hardware-independent policy only: this class never calls a GPIO or PWM driver.
class MotionSafety {
public:
    State state() const { return state_; }
    bool outputs_enabled() const { return state_ == State::Armed && inputs_.all_verified(); }
    const Positions& positions() const { return positions_; }
    const char* fault_reason() const { return reason_; }

    void update_inputs(const SafetyInputs& inputs) {
        inputs_ = inputs;
        if (state_ == State::Armed && !inputs_.all_verified()) fault("safety_input_lost");
    }

    const char* arm(std::uint32_t now_ms) {
        if (state_ != State::Disarmed) return "state_not_disarmed";
        if (!inputs_.calibration_valid) return "calibration_required";
        if (!inputs_.bench_approved) return "bench_approval_required";
        if (!inputs_.imu_valid) return "imu_required";
        if (!inputs_.physical_estop_clear) return "physical_estop_not_verified";
        if (!inputs_.output_backend_ready) return "motor_backend_disabled";
        // A future calibrated backend must establish measured starting positions
        // before requesting arm. This scaffold never enables that backend.
        state_ = State::Armed;
        last_command_ms_ = now_ms;
        return nullptr;
    }

    void disarm() {
        if (state_ == State::Armed) state_ = State::Disarmed;
        // Fault and emergency stop remain latched; commands cannot clear them.
    }

    void estop() { state_ = State::Estop; reason_ = "emergency_stop"; }

    void tick(std::uint32_t now_ms) {
        if (state_ == State::Armed && elapsed(now_ms, last_command_ms_) >= kWatchdogMs)
            fault("command_watchdog_expired");
    }

    const char* target(const Positions& next, std::uint32_t now_ms) {
        tick(now_ms);
        if (!outputs_enabled()) return "not_armed";
        const auto dt = elapsed(now_ms, last_command_ms_);
        if (dt == 0) return "target_too_soon";
        // Validate the complete frame before modifying any joint.
        for (std::size_t i = 0; i < kJointCount; ++i) {
            if (!std::isfinite(next[i])) return "nonfinite_target";
            if (next[i] < kMinDeg[i] || next[i] > kMaxDeg[i]) return "joint_limit";
            if (std::abs(next[i] - positions_[i]) > kMaxSpeedDegS * dt / 1000.0 + 1e-9)
                return "speed_limit";
        }
        positions_ = next;
        last_command_ms_ = now_ms;
        return nullptr;
    }

private:
    static std::uint32_t elapsed(std::uint32_t now, std::uint32_t then) { return now - then; }
    void fault(const char* reason) { state_ = State::Fault; reason_ = reason; }
    State state_ = State::Disarmed;
    SafetyInputs inputs_{};
    Positions positions_{{0, 20, 0, 0, 20, 0, 0, 0}};
    std::uint32_t last_command_ms_ = 0;
    const char* reason_ = "";
};

}  // namespace microduck
