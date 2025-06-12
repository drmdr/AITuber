import sounddevice as sd

print("List of available audio devices:")
devices = sd.query_devices()
for i, device in enumerate(devices):
    print(f"  Index {i}: {device['name']}")
    # 出力デバイスか入力デバイスかの情報も表示するとより分かりやすい
    if device['max_output_channels'] > 0:
        print(f"    Type: Output, Max Output Channels: {device['max_output_channels']}")
    if device['max_input_channels'] > 0:
        print(f"    Type: Input, Max Input Channels: {device['max_input_channels']}")
    if i == sd.default.device[0]: # Default input device
        print("    (Default Input Device)")
    if i == sd.default.device[1]: # Default output device
        print("    (Default Output Device)")
    print("-" * 20)
