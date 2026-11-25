import os
import sys
import subprocess
import zipfile
import re

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APK_PATH = os.path.join(WORKSPACE_ROOT, "mobile", "android", "app", "build", "outputs", "apk", "debug", "app-debug.apk")
TOOLS_DIR = os.path.join(WORKSPACE_ROOT, "tools")
JDK_DIR = os.path.join(TOOLS_DIR, "jdk-17")
SDK_DIR = os.path.join(TOOLS_DIR, "android-sdk")
APKSIGNER = os.path.join(SDK_DIR, "build-tools", "34.0.0", "apksigner.bat")
AAPT2 = os.path.join(SDK_DIR, "build-tools", "34.0.0", "aapt2.exe")

def run_cmd(cmd, env=None):
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

def get_env():
    env = os.environ.copy()
    env["JAVA_HOME"] = JDK_DIR
    env["ANDROID_HOME"] = SDK_DIR
    env["PATH"] = os.path.join(JDK_DIR, "bin") + os.pathsep + os.path.join(SDK_DIR, "build-tools", "34.0.0") + os.pathsep + env.get("PATH", "")
    return env

def audit():
    print("=" * 60)
    print("LOADLINK AI - APK SECURITY AUDIT")
    print(f"Target APK: {APK_PATH}")
    print("=" * 60)

    if not os.path.exists(APK_PATH):
        print(f"ERROR: APK not found at {APK_PATH}")
        return

    size_mb = os.path.getsize(APK_PATH) / (1024 * 1024)
    print(f"File size: {os.path.getsize(APK_PATH)} bytes ({size_mb:.2f} MB)")

    # 1. Signature verification
    print("\n[1] APKSIGNER CERTIFICATE & SIGNATURE VERIFICATION:")
    code, stdout, stderr = run_cmd([APKSIGNER, "verify", "--verbose", "--print-certs", APK_PATH], env=get_env())
    print(f"Exit code: {code}")
    print(stdout.strip())
    if stderr.strip():
        print("Error output:", stderr.strip())

    # 2. AAPT2 badging dump (Manifest & Permissions)
    print("\n[2] AAPT2 DUMP BADGING (MANIFEST, PERMISSIONS, PACKAGES):")
    code, stdout, stderr = run_cmd([AAPT2, "dump", "badging", APK_PATH], env=get_env())
    if code == 0:
        for line in stdout.splitlines():
            if any(k in line for k in ["package:", "sdkVersion:", "targetSdkVersion:", "uses-permission:", "uses-feature:", "application-label:", "launchable-activity:"]):
                print(" ", line)
    else:
        print("AAPT2 error:", stderr.strip())

    # 3. Merged AndroidManifest inspection
    print("\n[3] INSPECTING MERGED ANDROIDMANIFEST.XML:")
    merged_manifest_path = os.path.join(WORKSPACE_ROOT, "mobile", "android", "app", "build", "intermediates", "merged_manifest", "debug", "processDebugMainManifest", "AndroidManifest.xml")
    if not os.path.exists(merged_manifest_path):
        merged_manifest_path = os.path.join(WORKSPACE_ROOT, "mobile", "android", "app", "build", "intermediates", "merged_manifests", "debug", "AndroidManifest.xml")
    
    if os.path.exists(merged_manifest_path):
        print(f"Found merged manifest at: {merged_manifest_path}")
        with open(merged_manifest_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Find permissions
            perms = re.findall(r'<uses-permission\s+android:name="([^"]+)"', content)
            print("Declared Permissions (Total: %d):" % len(perms))
            for p in perms:
                print("   *", p)
            
            # Find exported components
            print("\nComponent Exported Status:")
            for tag in ["activity", "service", "receiver", "provider"]:
                matches = re.findall(rf'<{tag}[^>]*android:name="([^"]+)"[^>]*android:exported="([^"]+)"', content)
                for name, exp in matches:
                    print(f"   * <{tag}> {name} -> exported={exp}")
            
            # Check cleartext
            cleartext = re.findall(r'android:usesCleartextTraffic="([^"]+)"', content)
            print("\nCleartext traffic:", cleartext if cleartext else "Not declared (defaults to false on API 28+)")
    else:
        print("Merged manifest not found. Reading source AndroidManifest.xml:")
        source_manifest = os.path.join(WORKSPACE_ROOT, "mobile", "android", "app", "src", "main", "AndroidManifest.xml")
        with open(source_manifest, "r", encoding="utf-8") as f:
            print(f.read())

    # 4. Strings & URL scan in DEX files
    print("\n[4] HARDCODED URL & SECRETS SCAN IN DEX:")
    with zipfile.ZipFile(APK_PATH, 'r') as zf:
        dex_names = [n for n in zf.namelist() if n.endswith('.dex')]
        print(f"Scanning {len(dex_names)} DEX files for URLs, IPs, and sensitive keywords...")
        found_urls = set()
        found_keys = set()
        for d in dex_names:
            data = zf.read(d)
            # Find http/https strings
            raw_urls = re.findall(b'https?://[a-zA-Z0-9.\-_:/~?#@!$&\'()*+,;=%]+', data)
            for u in raw_urls:
                try:
                    us = u.decode('utf-8', errors='ignore')
                    if not any(ign in us for ign in ["schemas.android.com", "w3.org", "apache.org", "github.com/google"]):
                        found_urls.add(us)
                except:
                    pass
            # Check for API keys
            raw_keys = re.findall(b'(?i)(?:api_key|secret|password|bearer|auth_token)["\'\s:=]+([a-zA-Z0-9_\-]{8,})', data)
            for k in raw_keys:
                found_keys.add(k.decode('utf-8', errors='ignore'))
        
        print("Detected non-standard URLs/Endpoints:")
        for u in sorted(list(found_urls))[:20]:
            print("   *", u)
        
        print("Detected potential keys/secrets:", list(found_keys) if found_keys else "None detected")

if __name__ == "__main__":
    audit()
