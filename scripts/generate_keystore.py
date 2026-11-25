import os
import sys
import subprocess
import secrets
import string

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ANDROID_DIR = os.path.join(WORKSPACE_ROOT, "mobile", "android")
KEYSTORE_DIR = os.path.join(ANDROID_DIR, "keystore")
KEYSTORE_FILE = os.path.join(KEYSTORE_DIR, "loadlink-signing.jks")
PROPERTIES_FILE = os.path.join(ANDROID_DIR, "keystore.properties")
TOOLS_DIR = os.path.join(WORKSPACE_ROOT, "tools")
KEYTOOL = os.path.join(TOOLS_DIR, "jdk-17", "bin", "keytool.exe")

def generate_random_password(length=24):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_keystore():
    os.makedirs(KEYSTORE_DIR, exist_ok=True)
    if os.path.exists(KEYSTORE_FILE):
        print(f"Keystore already exists at {KEYSTORE_FILE}")
        return

    password = generate_random_password()
    dname = "CN=LoadLink Logistics Mobile Engineering, OU=Fleet Operations, O=LoadLink Freight AI, L=Kolkata, ST=West Bengal, C=IN"
    
    cmd = [
        KEYTOOL,
        "-genkeypair",
        "-v",
        "-keystore", KEYSTORE_FILE,
        "-alias", "loadlink-key",
        "-keyalg", "RSA",
        "-keysize", "2048",
        "-validity", "10000",
        "-dname", dname,
        "-storepass", password,
        "-keypass", password
    ]
    
    print("Generating dedicated RSA-2048 keystore...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Error generating keystore:", res.stderr)
        sys.exit(res.returncode)
    
    print(f"Generated keystore successfully: {KEYSTORE_FILE}")
    
    # Write keystore.properties (ignored by git)
    with open(PROPERTIES_FILE, "w") as f:
        f.write(f"storeFile={KEYSTORE_FILE.replace('\\', '/')}\n")
        f.write(f"storePassword={password}\n")
        f.write(f"keyAlias=loadlink-key\n")
        f.write(f"keyPassword={password}\n")
    
    print(f"Wrote keystore credentials to untracked: {PROPERTIES_FILE}")

    # Print certificate SHA-256 fingerprint
    cert_cmd = [KEYTOOL, "-list", "-v", "-keystore", KEYSTORE_FILE, "-alias", "loadlink-key", "-storepass", password]
    cert_res = subprocess.run(cert_cmd, capture_output=True, text=True)
    for line in cert_res.stdout.splitlines():
        if "SHA256:" in line or "SHA1:" in line or "Owner:" in line:
            print("  ", line.strip())

if __name__ == "__main__":
    generate_keystore()
