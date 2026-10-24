# Development validation scope

The host package was installed editable in a local Python 3.12 virtual
environment and exercised without hardware, credentials or external services.
It has no third-party runtime dependencies. Tests run with standard-library
`unittest`; CAD generation dependencies are separate in `requirements.txt`.

| Check | Result |
|---|---|
| Host configuration, command boundaries, bounded simulation, watchdog/stop, cloud proposal allowlist, budget and CLI tests | 19 tests passed |
| Native C++ safety policy | Six scenarios passed |
| Native C++ request parser against actual ArduinoJson 7.3.1 headers | Passed valid frames and malformed/schema/size/sequence/nonfinite/duplicate-key cases |
| Configuration inspection and deterministic head-scan demonstration | Ran successfully; eight simulated joints, no valid IMU claimed |
| ESP32 PlatformIO build | Attempted; blocked fetching the platform/toolchain from the registry, HTTP 403 |
| CI Python version matrix and ESP32 build job | Defined; remote results not verified |
| Pi, ESP32, UART wiring, MPU6050, power interlocks, servos, camera/audio/cloud services | Not hardware tested |
| Balance, locomotion and new mechanical fits | Not implemented or validated |

Repeat from the checkout root:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m microduck check-config
.venv/bin/python -m microduck simulate --duration 0.1
sh firmware/test_native.sh
```

For parser tests, install the pinned ArduinoJson dependency through PlatformIO
and run `sh firmware/test_protocol.sh`, or provide a trusted header directory
via `ARDUINOJSON_INCLUDE_DIR`. The local check used the upstream Git repository
at `e03d8ae8857098b377fb5c95b9b2357ebf15ddff` (v7.3.1). CI checks out that same
commit for native parser tests. The repository does not vendor those headers.

## ESP32 build prerequisite

PlatformIO Core 6.1.18 installed successfully, but the cloud proxy denied
`api.registry.platformio.org` and `registry.platformio.org`. Those dependency
hosts need access in environment settings before retrying; subsequent artifact
hosts may also need to be allowed as reported by PlatformIO. No signature,
checksum or TLS verification was disabled. GitHub availability alone does not
establish PlatformIO registry access.

The pinned build-only command, with PlatformIO installed in its isolated venv:

```bash
PLATFORMIO_CORE_DIR=/tmp/microduck-platformio .venv-firmware/bin/pio run -d firmware
```

This command does not flash a board. A successful compile would still not prove
electrical behavior, hardware commissioning or balancing. Do not remove the
output inhibition to work around missing calibration or failed checks.

## Existing CAD and archive

The original `microduck-cad.zip` already in the checkout was inspected with a
ZIP integrity check. It contains the original STEP, STL and CAD source. Its
geometry, exports, licenses and archived source were preserved unchanged.
The uploaded attachment exceeded the executor's 32 MiB transfer limit, so no
new extraction or comparison against that upload was possible. The existing
repository archive was used only as a visual design reference, not as verified
eight-servo mechanics or as instructions overriding the prototype request.
