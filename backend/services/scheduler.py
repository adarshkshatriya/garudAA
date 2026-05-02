import threading
import time
from services.checker import run_all_checks

_thread = None
_stop_event = threading.Event()
CHECK_INTERVAL = 60  # seconds


def _worker():
    print("[Scheduler] Background monitor thread started")
    while not _stop_event.is_set():
        try:
            results = run_all_checks()
            print(f"[Scheduler] Checked {len(results)} monitors")
        except Exception as e:
            print(f"[Scheduler] Error: {e}")
        _stop_event.wait(CHECK_INTERVAL)


def start_scheduler():
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_worker, daemon=True, name="SynthMonScheduler")
    _thread.start()


def stop_scheduler():
    _stop_event.set()
