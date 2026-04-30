import subprocess
import sys
import time
import shutil
import os
import signal


REPO_URL = "https://github.com/CSC132-CacheMoney/TBox.git"
BRANCH = "main"
CLONE_BASE = os.path.expanduser("~/Documents/Toolvault")
CHECK_INTERVAL = 300  # 5 minutes

current_process = None
current_clone_dir = None


def get_remote_sha():
    result = subprocess.run(
        ["git", "ls-remote", REPO_URL, f"refs/heads/{BRANCH}"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.split()[0]


def clone_repo(target_dir):
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    result = subprocess.run(
        ["git", "clone", "--depth=1", "--branch", BRANCH, REPO_URL, target_dir],
        capture_output=True, text=True, timeout=120
    )
    return result.returncode == 0


def start_app(clone_dir):
    main_py = os.path.join(clone_dir, "main.py")
    if not os.path.exists(main_py):
        print(f"[helper] main.py not found in {clone_dir}", flush=True)
        return None
    proc = subprocess.Popen([sys.executable, main_py], cwd=clone_dir)
    print(f"[helper] Started main.py (pid {proc.pid})", flush=True)
    return proc


def kill_process(proc):
    if proc is None:
        return
    try:
        os.kill(proc.pid, signal.SIGTERM)
        proc.wait(timeout=10)
        print(f"[helper] Stopped pid {proc.pid}", flush=True)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            proc.kill()
        except ProcessLookupError:
            pass


def main():
    global current_process, current_clone_dir

    print("[helper] Starting — performing initial clone...", flush=True)
    known_sha = get_remote_sha()
    if known_sha is None:
        print("[helper] Could not reach remote. Check network/URL.", flush=True)
        sys.exit(1)

    current_clone_dir = os.path.join(CLONE_BASE, "active")
    if clone_repo(current_clone_dir):
        current_process = start_app(current_clone_dir)
    else:
        print("[helper] Initial clone failed.", flush=True)
        sys.exit(1)

    print(f"[helper] Watching {BRANCH} every {CHECK_INTERVAL}s. SHA={known_sha[:8]}", flush=True)

    while True:
        time.sleep(CHECK_INTERVAL)

        remote_sha = get_remote_sha()
        if remote_sha is None:
            print("[helper] Could not reach remote, skipping check.", flush=True)
            continue

        if remote_sha == known_sha:
            continue

        print(f"[helper] Change detected: {known_sha[:8]} -> {remote_sha[:8]}", flush=True)
        print("[helper] Cloning new version...", flush=True)

        new_clone_dir = os.path.join(CLONE_BASE, "staging")
        if not clone_repo(new_clone_dir):
            print("[helper] Clone failed, keeping current version.", flush=True)
            continue

        print("[helper] Clone succeeded. Stopping old process...", flush=True)
        kill_process(current_process)

        # Replace active with new clone
        old_dir = os.path.join(CLONE_BASE, "old")
        if os.path.exists(old_dir):
            shutil.rmtree(old_dir)
        if os.path.exists(current_clone_dir):
            os.rename(current_clone_dir, old_dir)
        os.rename(new_clone_dir, current_clone_dir)
        if os.path.exists(old_dir):
            shutil.rmtree(old_dir)

        current_process = start_app(current_clone_dir)
        known_sha = remote_sha
        print(f"[helper] Running new version. SHA={known_sha[:8]}", flush=True)


if __name__ == "__main__":
    main()
