# Installation

## Requirements

- Python 3.8 or later
- `hid` Python package (hidapi bindings)
- A PS5 DualSense or DualSense Edge controller

```bash
pip install hid
```

---

## Linux

### 1. Install system hidapi

```bash
# Debian / Ubuntu
sudo apt install libhidapi-hidraw0

# Fedora / RHEL
sudo dnf install hidapi

# Arch
sudo pacman -S hidapi
```

### 2. Add udev rule (required for non-root access)

Without this rule you must run as root, which is not recommended.

```bash
sudo tee /etc/udev/rules.d/70-dualsense.rules <<'EOF'
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="054c", ATTRS{idProduct}=="0ce6", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="054c", ATTRS{idProduct}=="0df2", MODE="0666"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger
```

Reconnect the controller after applying the rule.

### 3. Pair the controller over Bluetooth

```bash
bluetoothctl
> power on
> agent on
> scan on
```

On the controller, hold **PS + Create** simultaneously until the light bar
blinks rapidly (pairing mode).

```bash
> pair XX:XX:XX:XX:XX:XX
> connect XX:XX:XX:XX:XX:XX
> trust XX:XX:XX:XX:XX:XX
> exit
```

Verify the device is visible:

```bash
python -c "from pydualsense.transport.discovery import list_controllers; print(list_controllers())"
```

### 4. Install pydualsense

```bash
# From source
git clone https://github.com/your-org/PyDualsenseBT
cd PyDualsenseBT
pip install -e .
```

---

## Windows

### 1. Install Python and pip dependencies

```powershell
pip install hid
```

The `hid` package bundles the hidapi DLL on Windows, so no separate system
install is required.

### 2. Connect the controller

**Bluetooth:**

1. Open **Settings → Bluetooth & devices → Add device**
2. Hold **PS + Create** on the controller until the light bar blinks
3. Select "Wireless Controller" from the device list

**USB:**

Connect via USB-C cable.  Windows will install the standard HID driver
automatically.

> Note: Do **not** install ViGEmBus or DS4Windows if you want raw HID access.
> Those tools intercept the device and prevent direct communication.

### 3. Verify

```powershell
python -c "from pydualsense.transport.discovery import list_controllers; print(list_controllers())"
```

---

## macOS

### 1. Install hidapi via Homebrew

```bash
brew install hidapi
pip install hid
```

### 2. Pair the controller

1. Open **System Settings → Bluetooth**
2. Hold **PS + Create** on the controller
3. Click "Wireless Controller" in the device list

### 3. Grant Input Monitoring permissions (macOS 10.15+)

If the terminal or Python binary is blocked from reading HID devices:

1. Open **System Settings → Privacy & Security → Input Monitoring**
2. Add your terminal application (Terminal, iTerm2, VS Code, etc.)

### 4. Verify

```bash
python -c "from pydualsense.transport.discovery import list_controllers; print(list_controllers())"
```

---

## Optional: numpy for IMU filtering

```bash
pip install numpy
```

Used by `pydualsense.utils.filters.LowPassFilter3D` for smoothing
gyroscope and accelerometer data.

---

## Troubleshooting

| Symptom                             | Fix                                                          |
|-------------------------------------|--------------------------------------------------------------|
| `RuntimeError: No DualSense found`  | Check Bluetooth is connected; verify udev rule on Linux      |
| `OSError: [Errno 13] Permission denied` | Apply the udev rule and reconnect                        |
| Controller found but no data        | Unplug USB if testing BT; only one process can own HID       |
| `ImportError: hid`                  | `pip install hid`                                            |
| Windows: device not found           | Disable DS4Windows/ViGEmBus that may be intercepting         |
| macOS: no input                     | Add Python/Terminal to Input Monitoring in Privacy settings  |
