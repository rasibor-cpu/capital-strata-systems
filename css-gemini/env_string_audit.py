import os

def audit_env_string():
    # Manually parse the .env to see exactly what is inside the variable
    env_path = os.path.join(os.getcwd(), ".env")
    raw_val = ""
    
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if "COINBASE_KEY_JSON_PATH" in line:
                    raw_val = line.strip()
    
    print(f"--- Environment String Audit ---")
    print(f"Raw Line in .env: [{raw_val}]")
    
    # Check for the common ' (2)' or space issues
    path_only = raw_val.split('=')[-1] if '=' in raw_val else ""
    print(f"Extracted Path: [{path_only}]")
    
    if os.path.exists(path_only.strip().strip("'").strip('"')):
        print("Status: OS can find the file, but check for trailing spaces in .env")
    else:
        print("Status: FILE PATH INVALID - The string in .env does not match the disk.")

if __name__ == "__main__":
    audit_env_string()