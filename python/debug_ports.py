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

    # Check Output matching
    target_out = None
    for name in outputs:
        if "STM" in name or "MIDI Commander" in name:
            target_out = name
            break

    if target_out:
        print(f"Found target output: '{target_out}'")
        try:
            print("Attempting to open output...")
            outport = mido.open_output(target_out)
            print("  Output Open SUCCESS")
            outport.close()
            print("  Output Closed")
        except Exception as e:
            print(f"  [ERROR] Output Open FAILED: {e}")

else:
    print("No matching 'STM' or 'MIDI Commander' device found.")
