"""Server locale: serve l'interfaccia web e calcola il cruscotto dal file caricato."""
from __future__ import annotations

import io
import threading
import webbrowser
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

from .data import ErroreFormato, carica_costi, carica_deals
from .kpi import analizza, carica_config

STATIC = Path(__file__).with_name("static")


def crea_app() -> Flask:
    app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

    @app.get("/")
    def index():
        return send_from_directory(STATIC, "index.html")

    @app.get("/api/config")
    def config():
        c = carica_config()
        return jsonify({"target_mensile": c["target_mensile"], "correggi_date": c["correggi_date"],
                        "tasso_vittoria_stimato": c["tasso_vittoria_stimato"]})

    @app.post("/api/analizza")
    def api_analizza():
        f = request.files.get("file")
        if f is None:
            return jsonify({"errore": "Nessun file caricato."}), 400
        try:
            cfg = carica_config()
            if request.form.get("target"):
                cfg["target_mensile"] = float(request.form["target"])
            if request.form.get("correggi_date") in ("true", "false"):
                cfg["correggi_date"] = request.form["correggi_date"] == "true"
            if request.form.get("tasso_vittoria"):
                cfg["tasso_vittoria_stimato"] = float(request.form["tasso_vittoria"])
            raw = f.read()
            d = carica_deals(io.BytesIO(raw), cfg)
            costi = carica_costi(io.BytesIO(raw))
            mese_s = request.form.get("mese")  # YYYY-MM
            if mese_s:
                mese = pd.Timestamp(mese_s + "-01")
            else:
                mese = d["mese_firma"].dropna().max()
            ctrl_s = request.form.get("controllo")
            if ctrl_s:
                controllo = pd.Timestamp(ctrl_s)
            else:
                controllo = (mese + pd.offsets.MonthEnd(0))
            out = analizza(d, costi, cfg, mese, controllo)
            out["mesi_disponibili"] = sorted(d["mese_firma"].dropna().dt.strftime("%Y-%m").unique())
            return jsonify(out)
        except ErroreFormato as e:
            return jsonify({"errore": str(e)}), 422
        except Exception as e:  # file corrotto o inatteso
            return jsonify({"errore": f"Impossibile leggere il file: {e}"}), 500

    return app


def avvia(host: str = "127.0.0.1", port: int = 8765, apri_browser: bool = True) -> None:
    app = crea_app()
    if apri_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    print(f"RevOps Monitor attivo su http://{host}:{port}  (Ctrl+C per chiudere)")
    app.run(host=host, port=port, debug=False)
