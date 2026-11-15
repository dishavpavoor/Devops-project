import fcntl
import os
import time
from pathlib import Path

DISK = Path("/demo-disk")
CHUNK = b"\0" * (1024 * 1024)


def main():
    if os.getenv("METRICS_SOURCE", "local") != "local":
        raise SystemExit("Disk fill is available only in demo mode.")
    size = os.statvfs(DISK)
    if not 20 * 1024**2 <= size.f_blocks * size.f_frsize <= 32 * 1024**2:
        raise SystemExit("Expected a dedicated 20–32 MiB demo filesystem.")
    if not os.path.ismount(DISK):
        raise SystemExit("Expected the dedicated /demo-disk mount.")

    with (DISK / ".demo.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("A disk demo is already running.") from None

        target = DISK / "demo-fill.bin"
        try:
            with target.open("wb", buffering=0) as output:
                for megabytes in range(1, 24):
                    output.write(CHUNK)
                    print(f"{megabytes}/24 MiB written", flush=True)
                    time.sleep(2)
                print("Holding at about 96% for 12 seconds", flush=True)
                time.sleep(12)
        finally:
            target.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
