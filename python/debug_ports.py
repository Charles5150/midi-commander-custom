import mido
import sys

print("Mido Backend:", mido.backend.name)

print("\n--- Input Ports ---")
inputs = mido.get_input_names()
for name in inputs:
    print(f"  '{name}'")

print("\n--- Output Ports ---")
outputs = mido.get_output_names()
for name in outputs:
    print(f"  '{name}'")

print("\n--- Connection Test ---")
target_name = None
for name in inputs:
    if "STM" in name or "MIDI Commander" in name:
        target_name = name
        break

if target_name:
    print(f"Found target input: '{target_name}'")
    try:
        print("Attempting to open input...")
        inport = mido.open_input(target_name)
        print("  Input Open SUCCESS")
        inport.close()
        print("  Input Closed")
    except Exception as e:
        print(f"  [ERROR] Input Open FAILED: {e}")

else:
    print("No matching 'STM' or 'MIDI Commander' device found.")
