"""Avvio del programma: python run.py  (apre il browser su http://127.0.0.1:8765)."""
import argparse

from revops_monitor.server import avvia

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="RevOps Monitor")
    p.add_argument("--porta", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true", help="non aprire il browser automaticamente")
    a = p.parse_args()
    avvia(port=a.porta, apri_browser=not a.no_browser)
