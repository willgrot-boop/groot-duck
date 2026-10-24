#pragma once

#include <ArduinoJson.h>
#include <cstddef>
#include <cstdint>
#include <cstring>

#include "motion_safety.hpp"

namespace microduck {
constexpr std::size_t kMaxLineBytes = 512;
enum class Command { Status, Disarm, Estop, Arm, Target };
struct Request {
    std::uint32_t seq = 0;
    Command command = Command::Status;
    Positions positions{};
};

inline bool one_complete_object(const char* line, std::size_t length) {
    bool string = false, escaped = false, started = false, complete = false;
    std::size_t depth = 0;
    for (std::size_t i = 0; i < length; ++i) {
        const char ch = line[i];
        const bool whitespace = ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n';
        if (complete) { if (!whitespace) return false; continue; }
        if (!started) {
            if (whitespace) continue;
            if (ch != '{') return false;
            started = true;
        }
        if (string) {
            if (escaped) escaped = false;
            else if (ch == '\\') escaped = true;
            else if (ch == '"') string = false;
        } else if (ch == '"') string = true;
        else if (ch == '{' || ch == '[') ++depth;
        else if (ch == '}' || ch == ']') {
            if (!depth) return false;
            if (!--depth) complete = true;
        }
    }
    return complete;
}

inline std::size_t unquoted_colons(const char* line, std::size_t length) {
    bool string = false, escaped = false;
    std::size_t count = 0;
    for (std::size_t i = 0; i < length; ++i) {
        const char ch = line[i];
        if (string) {
            if (escaped) escaped = false;
            else if (ch == '\\') escaped = true;
            else if (ch == '"') string = false;
        } else if (ch == '"') string = true;
        else if (ch == ':') ++count;
    }
    return count;
}

// Every valid schema object has a known member count. Counting member separators
// after JSON syntax validation catches duplicate keys (including escaped keys)
// that ArduinoJson would otherwise replace with their last value.
inline const char* decode_request(const char* line, std::size_t length, Request& out) {
    out = Request{};
    if (length > kMaxLineBytes) return "line_too_long";
    if (!one_complete_object(line, length)) return "invalid_json";
    JsonDocument doc;
    const auto parsed = deserializeJson(doc, line, length);
    if (parsed || !doc.is<JsonObject>()) return "invalid_json";
    if (!doc["seq"].is<std::uint32_t>() || doc["seq"].as<std::uint32_t>() > 0x7FFFFFFFU)
        return "invalid_sequence";
    out.seq = doc["seq"].as<std::uint32_t>();
    if (!doc["v"].is<int>() || doc["v"].as<int>() != 1) return "unsupported_version";
    if (!doc["type"].is<const char*>()) return "invalid_type";
    const char* type = doc["type"];
    if (!std::strcmp(type, "status")) out.command = Command::Status;
    else if (!std::strcmp(type, "disarm")) out.command = Command::Disarm;
    else if (!std::strcmp(type, "estop")) out.command = Command::Estop;
    else if (!std::strcmp(type, "arm")) out.command = Command::Arm;
    else if (!std::strcmp(type, "target")) out.command = Command::Target;
    else return "unknown_command";
    const bool target = out.command == Command::Target;
    if (doc.size() != (target ? 4U : 3U) || unquoted_colons(line, length) != (target ? 12U : 3U))
        return "unexpected_or_duplicate_fields";
    if (!target) return nullptr;
    const auto targets = doc["positions_deg"].as<JsonObjectConst>();
    if (targets.isNull() || targets.size() != kJointCount) return "all_eight_joints_required";
    for (std::size_t i = 0; i < kJointCount; ++i) {
        const auto value = targets[kJointNames[i]];
        if (!value.is<double>() || !std::isfinite(value.as<double>())) return "invalid_joint_target";
        out.positions[i] = value.as<double>();
    }
    return nullptr;
}
}  // namespace microduck
