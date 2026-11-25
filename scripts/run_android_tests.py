import os
import sys
import subprocess

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ANDROID_DIR = os.path.join(WORKSPACE_ROOT, "mobile", "android")
TOOLS_DIR = os.path.join(WORKSPACE_ROOT, "tools")
JDK_DIR = os.path.join(TOOLS_DIR, "jdk-17")
SDK_DIR = os.path.join(TOOLS_DIR, "android-sdk")
GRADLEW_BAT = os.path.join(ANDROID_DIR, "gradlew.bat")

def get_env():
    env = os.environ.copy()
    env["JAVA_HOME"] = JDK_DIR
    env["ANDROID_HOME"] = SDK_DIR
    env["ANDROID_SDK_ROOT"] = SDK_DIR
    env["PATH"] = os.path.join(JDK_DIR, "bin") + os.pathsep + os.path.join(SDK_DIR, "cmdline-tools", "latest", "bin") + os.pathsep + env.get("PATH", "")
    return env

def run_tests():
    env = get_env()
    print("=== Running Android Unit Tests (testDebugUnitTest) ===")
    cmd = [GRADLEW_BAT, "testDebugUnitTest", "--stacktrace"]
    print("Command:", " ".join(cmd))
    
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
    print(f"\n=== Android Unit Tests Finished with Exit Code: {proc.returncode} ===")
    return proc.returncode

if __name__ == "__main__":
    code = run_tests()
    sys.exit(code)
