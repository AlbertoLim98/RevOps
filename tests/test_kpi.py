"""Test: la logica deve restituire i numeri verificati sull'export di esempio e correggere le date."""
import datetime as dt
import os

import pandas as pd
import pytest

from revops_monitor.data import fix_data
from revops_monitor.kpi import analizza, carica_config, stato

EXPORT = os.environ.get("REVOPS_EXPORT")


def test_fix_data_scambia_giorno_e_mese_nelle_celle_data():
    assert fix_data(dt.datetime(2025, 1, 9)) == pd.Timestamp(2025, 9, 1)


def test_fix_data_non_tocca_giorno_maggiore_di_12():
    assert fix_data(dt.datetime(2025, 3, 25)) == pd.Timestamp(2025, 3, 25)


def test_fix_data_testo_gg_mm_aaaa():
    assert fix_data("09/01/2025") == pd.Timestamp(2025, 1, 9)


def test_fix_data_senza_correzione():
    assert fix_data(dt.datetime(2025, 1, 9), correggi=False) == pd.Timestamp(2025, 1, 9)


def test_fix_data_vuoto():
    assert pd.isna(fix_data(None))


@pytest.mark.parametrize("v,d,att,all_,atteso", [
    (0.9, "alto", 1.0, 0.85, "ATTENZIONE"), (0.8, "alto", 1.0, 0.85, "ALLARME"), (1.1, "alto", 1.0, 0.85, "OK"),
    (0.6, "basso", 0.4, 0.5, "ALLARME"), (0.45, "basso", 0.4, 0.5, "ATTENZIONE"), (0.3, "basso", 0.4, 0.5, "OK"),
    (None, "alto", 1.0, 0.85, "N.D."),
])
def test_stato(v, d, att, all_, atteso):
    assert stato(v, d, att, all_) == atteso


@pytest.mark.skipif(not EXPORT, reason="impostare REVOPS_EXPORT con il percorso dell'export di esempio")
def test_numeri_aprile_2026():
    from revops_monitor.data import carica_costi, carica_deals
    cfg = carica_config()
    d, c = carica_deals(EXPORT, cfg), carica_costi(EXPORT)
    r = analizza(d, c, cfg, pd.Timestamp("2026-04-01"), pd.Timestamp("2026-04-30"))
    apr, ott = r["trend"][-1], r["trend"][1]
    assert apr["won"] == 65
    assert round(apr["new_mrr"]) == 147806
    assert apr["closer"] == 21 and ott["closer"] == 15
    assert round(ott["lead_opp"], 3) == 0.246 and round(apr["lead_opp"], 3) == 0.174
    assert round(apr["cpl_meta"]) == 120 and round(apr["cpl_google"]) == 376
    quota4 = next(s for s in r["semaforo"] if s["id"] == "ultimi_4_giorni")["valore"]
    assert round(quota4, 2) == 0.58
