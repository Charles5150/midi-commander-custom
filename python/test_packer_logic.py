def safe_int(val, default=0):
    try:
        if val is None or str(val).strip() == "":
            return default
        return int(float(str(val)))
    except:
        return default


def get_hid_code(val):
    # If it's already a number, return it
    s_val = str(val).strip()
    if s_val.isdigit():
        return int(s_val)

    # Check for single char
    if len(s_val) == 1:
        c = s_val.lower()
        if "a" <= c <= "z":
            return 4 + (ord(c) - ord("a"))
        if "1" <= c <= "9":
            return 30 + (int(c) - 1)
        if c == "0":
            return 39

    return 0


print(f"safe_int('5.0') = {safe_int('5.0')}")
print(f"safe_int('127') = {safe_int('127')}")
print(f"safe_int('') = {safe_int('')}")
print(f"safe_int('nan') = {safe_int('nan')}")

print(f"get_hid_code('a') = {get_hid_code('a')}")
print(f"get_hid_code('z') = {get_hid_code('z')}")
print(f"get_hid_code('1') = {get_hid_code('1')}")
print(f"get_hid_code('0') = {get_hid_code('0')}")
