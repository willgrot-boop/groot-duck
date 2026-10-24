#include "protocol.hpp"
#include <cassert>
#include <iostream>
#include <string>

using namespace microduck;
namespace {
const char* parse(const std::string& text, Request& request) {
    return decode_request(text.data(), text.size(), request);
}
void invalid(const std::string& text) {
    Request request;
    assert(parse(text, request) != nullptr);
}
}  // namespace

int main() {
    Request request;
    assert(!parse(R"({"v":1,"seq":123,"type":"status"})", request));
    assert(request.seq == 123 && request.command == Command::Status);
    for (const auto* type : {"arm", "disarm", "estop"}) {
        assert(!parse(std::string("{\"v\":1,\"seq\":1,\"type\":\"") + type + "\"}", request));
    }
    const std::string target = R"({"v":1,"seq":7,"type":"target","positions_deg":{"left_hip_pitch":0,"left_knee":20,"left_ankle_pitch":0,"right_hip_pitch":0,"right_knee":20,"right_ankle_pitch":0,"head_pan":0,"head_tilt":0}})";
    assert(!parse(target, request));
    assert(request.command == Command::Target && request.positions[1] == 20);
    invalid("{}");
    invalid("[]");
    invalid("garbage");
    invalid(R"({"v":1,"seq":1,"type":"status"}garbage)");
    invalid(R"({"v":1,"seq":1,"type":"status"}{})");
    invalid(R"({"v":1,"seq":-1,"type":"status"})");
    invalid(R"({"v":1,"seq":2147483648,"type":"status"})");
    invalid(R"({"v":true,"seq":1,"type":"status"})");
    invalid(R"({"v":1,"seq":true,"type":"status"})");
    invalid(R"({"v":2,"seq":1,"type":"status"})");
    invalid(R"({"v":1,"seq":1,"type":"dance"})");
    invalid(R"({"v":1,"seq":1,"type":"arm","calibration_valid":true})");
    invalid(R"({"v":1,"seq":1,"type":"status","seq":2})");
    invalid(R"({"v":1,"seq":1,"type":"status","\u0076":1})");
    invalid(R"({"v":1,"seq":1,"type":"target","positions_deg":{}})");
    auto duplicate = target;
    duplicate.insert(duplicate.size() - 2, ",\"head_tilt\":1");
    invalid(duplicate);
    auto nonfinite = target;
    nonfinite.replace(nonfinite.find("\"head_tilt\":0"), 13, "\"head_tilt\":1e1000");
    invalid(nonfinite);
    auto boolean = target;
    boolean.replace(boolean.find("\"head_tilt\":0"), 13, "\"head_tilt\":false");
    invalid(boolean);
    invalid(std::string(513, ' '));
    std::cout << "Firmware protocol cases passed (valid frames, malformed/schema/size/sequence/nonfinite/duplicate rejection)\n";
}
