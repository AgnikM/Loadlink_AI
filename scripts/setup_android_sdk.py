import os
import sys
import shutil
import zipfile
import urllib.request
import subprocess

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS_DIR = os.path.join(WORKSPACE_ROOT, "tools")
JDK_DIR = os.path.join(TOOLS_DIR, "jdk-17")
SDK_DIR = os.path.join(TOOLS_DIR, "android-sdk")

JDK_URL = "https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse?project=jdk"
CMDLINE_TOOLS_URL = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"

def download_file(url, target_path, description):
    print(f"Downloading {description} from {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as response, open(target_path, "wb") as out_file:
        total_length = response.headers.get("Content-Length")
        if total_length:
            total_length = int(total_length)
        downloaded = 0
        chunk_size = 1024 * 1024 * 4  # 4MB chunks
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            downloaded += len(chunk)
            out_file.write(chunk)
            if total_length:
                percent = int(downloaded * 100 / total_length)
                print(f"  {description}: {percent}% ({downloaded // (1024*1024)} MB / {total_length // (1024*1024)} MB)", end="\r")
    print(f"\nCompleted {description} download: {target_path}")

def setup_jdk():
    java_exe = os.path.join(JDK_DIR, "bin", "java.exe")
    if os.path.exists(java_exe):
        print(f"JDK 17 already exists at {JDK_DIR}")
        return JDK_DIR
    
    os.makedirs(TOOLS_DIR, exist_ok=True)
    zip_path = os.path.join(TOOLS_DIR, "jdk17.zip")
    if not os.path.exists(zip_path):
        download_file(JDK_URL, zip_path, "Temurin OpenJDK 17")
    
    print("Extracting JDK 17...")
    temp_extract = os.path.join(TOOLS_DIR, "jdk_temp")
    if os.path.exists(temp_extract):
        shutil.rmtree(temp_extract)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_extract)
    
    # Identify top level dir in zip (e.g., jdk-17.0.21+1)
    extracted_items = os.listdir(temp_extract)
    if extracted_items and os.path.isdir(os.path.join(temp_extract, extracted_items[0])):
        inner_dir = os.path.join(temp_extract, extracted_items[0])
        if os.path.exists(JDK_DIR):
            shutil.rmtree(JDK_DIR)
        shutil.move(inner_dir, JDK_DIR)
        shutil.rmtree(temp_extract)
    else:
        shutil.move(temp_extract, JDK_DIR)
    
    if os.path.exists(zip_path):
        os.remove(zip_path)
    print(f"JDK 17 successfully installed to {JDK_DIR}")
    return JDK_DIR

def setup_cmdline_tools():
    sdkmanager_bat = os.path.join(SDK_DIR, "cmdline-tools", "latest", "bin", "sdkmanager.bat")
    if os.path.exists(sdkmanager_bat):
        print(f"Android cmdline-tools already exist at {sdkmanager_bat}")
        return SDK_DIR
    
    os.makedirs(TOOLS_DIR, exist_ok=True)
    zip_path = os.path.join(TOOLS_DIR, "cmdline_tools.zip")
    if not os.path.exists(zip_path):
        download_file(CMDLINE_TOOLS_URL, zip_path, "Android Command Line Tools")
    
    print("Extracting Android Command Line Tools...")
    temp_extract = os.path.join(TOOLS_DIR, "cmdline_temp")
    if os.path.exists(temp_extract):
        shutil.rmtree(temp_extract)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_extract)
    
    # Top level is cmdline-tools/
    extracted_cmdline = os.path.join(temp_extract, "cmdline-tools")
    latest_target = os.path.join(SDK_DIR, "cmdline-tools", "latest")
    os.makedirs(os.path.dirname(latest_target), exist_ok=True)
    if os.path.exists(latest_target):
        shutil.rmtree(latest_target)
    shutil.move(extracted_cmdline, latest_target)
    shutil.rmtree(temp_extract)
    
    if os.path.exists(zip_path):
        os.remove(zip_path)
    print(f"Command line tools installed to {latest_target}")
    return SDK_DIR

def install_platforms_and_build_tools():
    sdkmanager_bat = os.path.join(SDK_DIR, "cmdline-tools", "latest", "bin", "sdkmanager.bat")
    env = os.environ.copy()
    env["JAVA_HOME"] = JDK_DIR
    env["ANDROID_HOME"] = SDK_DIR
    env["PATH"] = f"{os.path.join(JDK_DIR, 'bin')};{os.path.join(SDK_DIR, 'cmdline-tools', 'latest', 'bin')};{env.get('PATH', '')}"
    
    print("Accepting SDK licenses...")
    license_proc = subprocess.Popen(
        [sdkmanager_bat, "--sdk_root=" + SDK_DIR, "--licenses"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env
    )
    # Send 'y\n' repeated
    license_out, _ = license_proc.communicate(input="y\ny\ny\ny\ny\ny\ny\ny\n")
    print("License output summary:", license_out.splitlines()[-3:] if license_out else "Done")
    
    print("Installing platforms;android-34 and build-tools;34.0.0...")
    install_proc = subprocess.run(
        [sdkmanager_bat, "--sdk_root=" + SDK_DIR, "platforms;android-34", "build-tools;34.0.0"],
        env=env,
        capture_output=True,
        text=True
    )
    print("Install stdout:", install_proc.stdout[-500:] if install_proc.stdout else "None")
    if install_proc.returncode != 0:
        print("Install stderr:", install_proc.stderr)
        sys.exit(install_proc.returncode)
    
    print("Platforms and build tools installed successfully.")

def write_local_properties():
    local_props_path = os.path.join(WORKSPACE_ROOT, "mobile", "android", "local.properties")
    sdk_dir_escaped = SDK_DIR.replace("\\", "\\\\")
    with open(local_props_path, "w") as f:
        f.write(f"sdk.dir={sdk_dir_escaped}\n")
    print(f"Wrote local.properties to {local_props_path}")

if __name__ == "__main__":
    setup_jdk()
    setup_cmdline_tools()
    install_platforms_and_build_tools()
    write_local_properties()
    print("=== Android SDK and JDK 17 Setup Complete ===")
