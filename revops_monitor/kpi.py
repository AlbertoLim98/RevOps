"""Calcolo degli indicatori del cruscotto (stessa logica del file Excel di monitoraggio)."""
from __future__ import annotations

import calendar
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .data import costo, fine_mese

CONFIG_PATH = Path(__file__).with_name("config.json")
RUOLI_META = ["AE IB FC", "BDR IB", "BDR OB SMB", "BDR MM", "OBFC", "AE MM"]
CANALI = ["Meta paid", "Google paid", "Altri paid", "Outbound e outreach", "Altri canali"]
RUOLI_CHIUSURA = ["AE IB FC", "AE SMALL SMB", "AE LARGE SMB", "AE MM", "OBFC", "BDR OB SMB"]


def carica_config(percorso: Path | str | None = None) -> dict:
    with open(percorso or CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _mesi_prima(m: pd.Timestamp, k: int) -> pd.Timestamp:
    return m - pd.DateOffset(months=k)


def _num(x) -> float | None:
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except TypeError:
        pass
    return float(x)


def stato(valore: float | None, direzione: str, attenzione: float, allarme: float) -> str:
    if valore is None:
        return "N.D."
    if direzione == "alto":
        return "ALLARME" if valore < allarme else "ATTENZIONE" if valore < attenzione else "OK"
    return "ALLARME" if valore > allarme else "ATTENZIONE" if valore > attenzione else "OK"


def mrr_mese(d: pd.DataFrame, m: pd.Timestamp) -> float:
    w = d[(d["stage"] == "Won") & (d["mese_firma"] == m)]
    return float(w["mrr"].sum())


def pacing(d: pd.DataFrame, m: pd.Timestamp, controllo: pd.Timestamp) -> dict:
    won = d[d["stage"] == "Won"]
    giorni = calendar.monthrange(m.year, m.month)[1]
    serie_mese, serie_media = [], []
    for g in range(1, giorni + 1):
        fino = pd.Timestamp(year=m.year, month=m.month, day=g)
        serie_mese.append(float(won[(won["firma"] >= m) & (won["firma"] <= fino)]["mrr"].sum()))
        tot = 0.0
        for k in (1, 2, 3):
            p = _mesi_prima(m, k)
            gp = min(g, calendar.monthrange(p.year, p.month)[1])
            tot += float(won[(won["firma"] >= p) & (won["firma"] <= pd.Timestamp(year=p.year, month=p.month, day=gp))]["mrr"].sum())
        serie_media.append(tot / 3)
    return {"giorni": list(range(1, giorni + 1)), "mese": serie_mese, "media3": serie_media,
            "lineare": [None] * giorni}


def analizza(d: pd.DataFrame, costi: pd.DataFrame, config: dict, mese: pd.Timestamp,
             controllo: pd.Timestamp) -> dict:
    mese = pd.Timestamp(year=mese.year, month=mese.month, day=1)
    target = float(config["target_mensile"])
    win_rate = float(config["tasso_vittoria_stimato"])
    min_meta = float(config["min_lead_meta_ruolo"])
    soglia_meta = float(config["soglia_meta_opportunity_ruolo"])
    prev = _mesi_prima(mese, 1)
    eom = fine_mese(mese)
    giorno = min(controllo.day, eom.day) if (controllo.year, controllo.month) == (mese.year, mese.month) else eom.day

    # ---- pacing
    pc = pacing(d, mese, controllo)
    pc["lineare"] = [target * g / eom.day for g in pc["giorni"]]
    cum = pc["mese"][giorno - 1]
    media = pc["media3"][giorno - 1]
    pacing_val = _num(cum / media) if media else 0.0
    gap = target - cum

    # ---- copertura pipeline
    aperte = d[(d["stage"] == "Opportunity") & (d["closedate"] > controllo) & (d["closedate"] <= eom)]
    if gap <= 0:
        copertura, nota_cop = 1.0, "Target raggiunto"
    elif len(aperte) == 0:
        copertura, nota_cop = None, "Nessuna opportunity aperta con closedate nel resto del mese (export fatto dopo la fine del mese?)"
    else:
        copertura, nota_cop = float(aperte["mrr"].sum()) * win_rate / gap, ""

    # ---- slittamento
    won_m = d[(d["stage"] == "Won") & (d["mese_firma"] == mese)]
    mrr_m = float(won_m["mrr"].sum())
    ultimi4 = float(won_m[won_m["firma"] >= eom - pd.Timedelta(days=3)]["mrr"].sum())
    quota4 = ultimi4 / mrr_m if mrr_m else 0.0

    # ---- coorte del mese precedente
    c = d[d["mese_creazione"] == prev]
    con_opp = c[c["opportunity"].notna()]
    chiuse_vinte = len(con_opp[con_opp["stage"].isin(["Won", "Churn"])])
    chiuse_perse = len(con_opp[con_opp["stage"] == "Lost"])
    lead_opp = len(con_opp) / len(c) if len(c) else 0.0
    vitt = chiuse_vinte / (chiuse_vinte + chiuse_perse) if (chiuse_vinte + chiuse_perse) else 0.0
    cm = c[c["gruppo_canale"] == "Meta paid"]
    meta_lo = len(cm[cm["opportunity"].notna()]) / len(cm) if len(cm) else 0.0
    opp_meta = len(cm[cm["opportunity"].notna()])
    cg = c[c["gruppo_canale"] == "Google paid"]
    opp_google = len(cg[cg["opportunity"].notna()])
    c_opp_meta = costo(costi, "Meta Paid", prev) / opp_meta if opp_meta else 0.0
    c_opp_google = costo(costi, "Google Paid", prev) / opp_google if opp_google else 0.0

    # ---- ruoli Meta, ultimi 2 mesi completi
    due = d[(d["mese_creazione"] >= _mesi_prima(mese, 2)) & (d["mese_creazione"] <= prev) & (d["gruppo_canale"] == "Meta paid")]
    ruoli = []
    for r in RUOLI_META:
        x = due[due["ruolo_generatore"] == r]
        n, o = len(x), len(x[x["opportunity"].notna()])
        pct = o / n if n else 0.0
        seg = "BASSA RESA" if (n >= min_meta and pct < soglia_meta) else ("volume basso" if n < min_meta else "ok")
        ruoli.append({"ruolo": r, "lead_meta": n, "opportunity": o, "pct": pct, "segnale": seg})
    n_bassa = sum(1 for r in ruoli if r["segnale"] == "BASSA RESA")

    # ---- qualita' dei dati
    n_won = len(won_m)
    senza_bdr = (won_m["ruolo_generatore"] == "n.d.").sum() / n_won if n_won else 0.0
    senza_mrr = int(won_m["mrr"].isna().sum())
    open_opp = d[d["stage"] == "Opportunity"]
    scadute = (open_opp["closedate"] < controllo).sum() / len(open_opp) if len(open_opp) else 0.0
    obfc = c[c["ruolo_owner"] == "OBFC"]
    ae = c[c["ruolo_owner"] == "AE IB FC"]
    qualita = [
        {"controllo": "Righe con Deal ID nell'export", "valore": int(len(d)), "formato": "int", "nota": ""},
        {"controllo": "Deal senza ruolo del proprietario", "valore": float((d["ruolo_owner"] == "").mean()), "formato": "pct1", "nota": "Storico: 2,2%."},
        {"controllo": "Won del mese senza ruolo BDR", "valore": float(senza_bdr), "formato": "pct1", "nota": "Storico 2,8%: spesso deal da relazioni esistenti."},
        {"controllo": "Won del mese senza MRR (n.)", "valore": senza_mrr, "formato": "int", "nota": "Dovrebbe essere 0."},
        {"controllo": "Deal con MRR vuoto", "valore": float(d["mrr"].isna().mean()), "formato": "pct1", "nota": "Storico 46%, quasi tutto su Lost e New Deal."},
        {"controllo": "Date di creazione con giorno > 12 (n.)", "valore": int(d["data_giorno_creazione_gt12"].sum()), "formato": "int",
         "nota": "Se > 0 con la correzione attiva: l'export potrebbe non avere piu' giorno e mese invertiti. Provare 'correggi_date': false."},
        {"controllo": "Opportunity aperte con closedate passata", "valore": float(scadute), "formato": "pct1", "nota": "Closedate non aggiornate: la copertura e' meno affidabile."},
        {"controllo": "Deal OBFC senza chiamate registrate (coorte mese prec.)", "valore": float(obfc["chiamate"].isna().mean()) if len(obfc) else 0.0, "formato": "pct", "nota": "Dato di registrazione, non prova di mancato lavoro."},
        {"controllo": "Deal AE IB FC senza chiamate registrate (coorte mese prec.)", "valore": float(ae["chiamate"].isna().mean()) if len(ae) else 0.0, "formato": "pct", "nota": "Termine di confronto."},
    ]

    # ---- semaforo
    sc = config["soglie"]
    cost_sales = costo(costi, "Sales Cost Details", mese)
    valori = {
        "new_mrr_su_target": mrr_m / target if target else 0.0,
        "pacing": pacing_val,
        "ultimi_4_giorni": quota4,
        "copertura_pipeline": copertura,
        "mrr_per_costo_sales": mrr_m / cost_sales if cost_sales else None,
        "lead_opportunity": lead_opp,
        "vittorie_opportunity": vitt,
        "meta_lead_opportunity": meta_lo,
        "costo_opp_meta": c_opp_meta,
        "costo_opp_google": c_opp_google,
        "ruoli_bassa_resa": n_bassa,
        "won_senza_bdr": senza_bdr,
        "won_senza_mrr": senza_mrr,
        "closedate_scadute": scadute,
    }
    semaforo = []
    for k, s in sc.items():
        v = _num(valori[k])
        semaforo.append({"id": k, "etichetta": s["etichetta"], "valore": v, "formato": s["formato"],
                         "attenzione": s["attenzione"], "allarme": s["allarme"], "direzione": s["direzione"],
                         "stato": stato(v, s["direzione"], s["attenzione"], s["allarme"]),
                         "suggerimento": s["suggerimento"]})

    # ---- andamento 8 mesi
    trend = []
    for k in range(7, -1, -1):
        mm = _mesi_prima(mese, k)
        w = d[(d["stage"] == "Won") & (d["mese_firma"] == mm)]
        cc = d[d["mese_creazione"] == mm]
        co = cc[cc["opportunity"].notna()]
        wv = len(co[co["stage"].isin(["Won", "Churn"])])
        lp = len(co[co["stage"] == "Lost"])
        cs = costo(costi, "Sales Cost Details", mm)
        meta_n = len(cc[cc["gruppo_canale"] == "Meta paid"])
        goo_n = len(cc[cc["gruppo_canale"] == "Google paid"])
        meta_o = len(cc[(cc["gruppo_canale"] == "Meta paid") & cc["opportunity"].notna()])
        goo_o = len(cc[(cc["gruppo_canale"] == "Google paid") & cc["opportunity"].notna()])
        sm, sg = costo(costi, "Meta Paid", mm), costo(costi, "Google Paid", mm)
        riga = {
            "mese": mm.strftime("%Y-%m"),
            "new_mrr": float(w["mrr"].sum()), "target": target, "won": int(len(w)),
            "closer": int(w["owner"].nunique()), "costo_sales": cs,
            "mrr_per_costo": float(w["mrr"].sum()) / cs if cs else None,
            "deal_creati": int(len(cc)),
            "lead_opp": len(co) / len(cc) if len(cc) else 0.0,
            "lead_won": len(cc[cc["stage"] == "Won"]) / len(cc) if len(cc) else 0.0,
            "vitt_opp": wv / (wv + lp) if (wv + lp) else 0.0,
            "lead_meta": meta_n, "lead_google": goo_n,
            "spesa_meta": sm, "spesa_google": sg,
            "cpl_meta": sm / meta_n if meta_n else None, "cpl_google": sg / goo_n if goo_n else None,
            "cpo_meta": sm / meta_o if meta_o else None, "cpo_google": sg / goo_o if goo_o else None,
        }
        for ch in CANALI:
            riga["mrr_" + ch] = float(w[w["gruppo_canale"] == ch]["mrr"].sum())
        trend.append(riga)

    # ---- lead Meta per ruolo nel tempo
    meta_ruoli = []
    for k in range(7, -1, -1):
        mm = _mesi_prima(mese, k)
        x = d[(d["mese_creazione"] == mm) & (d["gruppo_canale"] == "Meta paid")]
        riga = {"mese": mm.strftime("%Y-%m")}
        tot = 0
        for r in RUOLI_META:
            n = int((x["ruolo_generatore"] == r).sum()); riga[r] = n; tot += n
        riga["Altri / non assegnato"] = int(len(x)) - tot
        meta_ruoli.append(riga)

    return {
        "mese": mese.strftime("%Y-%m"), "controllo": controllo.strftime("%Y-%m-%d"), "target": target,
        "semaforo": semaforo,
        "conteggio": {"allarmi": sum(1 for s in semaforo if s["stato"] == "ALLARME"),
                      "attenzioni": sum(1 for s in semaforo if s["stato"] == "ATTENZIONE")},
        "pacing": {**pc, "giorno": giorno, "cumulato": cum, "media3": media, "gap": gap,
                   "copertura": copertura, "nota_copertura": nota_cop,
                   "atteso_pipeline": float(aperte["mrr"].sum()) * win_rate,
                   "serie_media3": pc["media3"]},
        "trend": trend, "ruoli_meta": ruoli, "meta_per_ruolo": meta_ruoli, "qualita": qualita,
    }
