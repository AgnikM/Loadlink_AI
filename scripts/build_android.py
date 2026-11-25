import os
import sys
import subprocess

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ANDROID_DIR = os.path.join(WORKSPACE_ROOT, "mobile", "android")
TOOLS_DIR = os.path.join(WORKSPACE_ROOT, "tools")
JDK_DIR = os.path.join(TOOLS_DIR, "jdk-17")
SDK_DIR = os.path.join(TOOLS_DIR, "android-sdk")
GRADLE_BAT = os.path.join(TOOLS_DIR, "gradle-8.5", "bin", "gradle.bat")
GRADLEW_BAT = os.path.join(ANDROID_DIR, "gradlew.bat")
WRAPPER_JAR = os.path.join(ANDROID_DIR, "gradle", "wrapper", "gradle-wrapper.jar")

def get_env():
    env = os.environ.copy()
    env["JAVA_HOME"] = JDK_DIR
    env["ANDROID_HOME"] = SDK_DIR
    env["ANDROID_SDK_ROOT"] = SDK_DIR
    env["PATH"] = os.path.join(JDK_DIR, "bin") + os.pathsep + os.path.join(SDK_DIR, "cmdline-tools", "latest", "bin") + os.pathsep + env.get("PATH", "")
    return env

def ensure_wrapper():
    if not os.path.exists(WRAPPER_JAR):
        print("Generating Gradle wrapper using Gradle 8.5...")
        res = subprocess.run([GRADLE_BAT, "wrapper", "--gradle-version", "8.5"], cwd=ANDROID_DIR, env=get_env(), capture_output=True, text=True)
        print("Wrapper return code:", res.returncode)
        if res.returncode != 0:
            print("Wrapper error:", res.stderr)
            sys.exit(res.returncode)
    print("Gradle wrapper ready at:", WRAPPER_JAR)

def build_debug_apk():
    ensure_wrapper()
    env = get_env()
    print("=== Running Gradle assembleDebug ===")
    cmd = [GRADLEW_BAT, "assembleDebug", "--stacktrace"]
    print("Command:", " ".join(cmd))
    print("Working Dir:", ANDROID_DIR)
    print("JAVA_HOME:", env["JAVA_HOME"])
    print("ANDROID_HOME:", env["ANDROID_HOME"])
    
    proc = subprocess.Popen(
        cmd,
        cwd=ANDROID_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    full_output = []
    for line in proc.stdout:
        print(line, end="")
        full_output.append(line)
        
    proc.wait()
    print(f"\n=== Build Process Finished with Exit Code: {proc.returncode} ===")
    
    apk_dir = os.path.join(ANDROID_DIR, "app", "build", "outputs", "apk", "debug")
    apk_file = os.path.join(apk_dir, "app-debug.apk")
    if os.path.exists(apk_file):
        size_mb = os.path.getsize(apk_file) / (1024 * 1024)
        print(f"SUCCESS: Debug APK generated at:\n  {apk_file} ({size_mb:.2f} MB)")
    else:
        print(f"APK not found at expected location: {apk_file}")
    
    return proc.returncode

if __name__ == "__main__":
    code = build_debug_apk()
    sys.exit(code)
