#include "motion_safety.hpp"

#include <cassert>
#include <iostream>
#include <limits>
#include <string>

using namespace microduck;

namespace {
SafetyInputs verified() { return {true, true, true, true, true}; }

void boot_inhibits_and_requires_every_prerequisite() {
    MotionSafety controller;
    assert(controller.state() == State::Disarmed);
    assert(!controller.outputs_enabled());
    assert(std::string(controller.arm(0)) == "calibration_required");
    for (int missing = 0; missing < 5; ++missing) {
        MotionSafety c;
        auto inputs = verified();
        switch (missing) {
            case 0: inputs.calibration_valid = false; break;
            case 1: inputs.bench_approved = false; break;
            case 2: inputs.imu_valid = false; break;
            case 3: inputs.physical_estop_clear = false; break;
            case 4: inputs.output_backend_ready = false; break;
        }
        c.update_inputs(inputs);
        assert(c.arm(0) != nullptr);
        assert(!c.outputs_enabled());
    }
}

void invalid_frames_are_atomic_and_do_not_pet_watchdog() {
    MotionSafety c;
    c.update_inputs(verified());
    assert(c.arm(100) == nullptr);
    const auto initial = c.positions();
    auto target = initial;
    target[0] = 3;
    target[7] = std::numeric_limits<double>::quiet_NaN();
    assert(std::string(c.target(target, 200)) == "nonfinite_target");
    assert(c.positions() == initial);
    target[7] = 26;
    assert(std::string(c.target(target, 200)) == "joint_limit");
    assert(c.positions() == initial);
    target[7] = 0;
    target[0] = 30;
    assert(std::string(c.target(target, 200)) == "speed_limit");
    assert(c.positions() == initial);
    c.tick(600);
    assert(c.state() == State::Fault);
    assert(!c.outputs_enabled());
    c.disarm();
    assert(c.state() == State::Fault);
    assert(c.arm(700) != nullptr);
}

void valid_frame_updates_and_watchdog_disables_on_deadline() {
    MotionSafety c;
    c.update_inputs(verified());
    assert(c.arm(1000) == nullptr);
    auto target = c.positions();
    assert(std::string(c.target(target, 1000)) == "target_too_soon");
    target[0] = 6;
    assert(c.target(target, 1100) == nullptr);
    assert(c.positions() == target);
    c.tick(1599);
    assert(c.outputs_enabled());
    c.tick(1600);
    assert(c.state() == State::Fault);
    assert(!c.outputs_enabled());
    assert(std::string(c.fault_reason()) == "command_watchdog_expired");
}

void imu_loss_and_estop_latch() {
    MotionSafety c;
    c.update_inputs(verified());
    assert(c.arm(0) == nullptr);
    auto inputs = verified();
    inputs.imu_valid = false;
    c.update_inputs(inputs);
    assert(c.state() == State::Fault);
    assert(!c.outputs_enabled());
    c.estop();
    assert(c.state() == State::Estop);
    c.disarm();
    assert(c.state() == State::Estop);
    c.update_inputs(verified());
    assert(c.arm(1) != nullptr);
    assert(!c.outputs_enabled());
}

void watchdog_handles_clock_wrap() {
    MotionSafety c;
    c.update_inputs(verified());
    const auto start = std::numeric_limits<std::uint32_t>::max() - 99;
    assert(c.arm(start) == nullptr);
    c.tick(399);
    assert(c.outputs_enabled());
    c.tick(400);
    assert(!c.outputs_enabled());
}

void disarmed_targets_cannot_move_state() {
    MotionSafety c;
    auto next = c.positions();
    next[0] = 4;
    assert(std::string(c.target(next, 100)) == "not_armed");
    assert(c.positions()[0] == 0);
    c.update_inputs(verified());
    assert(c.arm(100) == nullptr);
    c.disarm();
    assert(c.state() == State::Disarmed);
    assert(!c.outputs_enabled());
}
}  // namespace

int main() {
    boot_inhibits_and_requires_every_prerequisite();
    invalid_frames_are_atomic_and_do_not_pet_watchdog();
    valid_frame_updates_and_watchdog_disables_on_deadline();
    imu_loss_and_estop_latch();
    watchdog_handles_clock_wrap();
    disarmed_targets_cannot_move_state();
    std::cout << "6 firmware safety scenarios passed\n";
}
