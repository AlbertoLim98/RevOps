"""Lettura e pulizia dell'export Excel del CRM (fogli 'Sales Deals DB' e 'Cost Data')."""
from __future__ import annotations

import calendar
import datetime as dt
import re
from typing import Any

import pandas as pd

MESI_IT = {"gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6,
           "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12}

# nome colonna dell'export -> nome interno
COLONNE = {
    "Deal ID": "id",
    "Deal Creation Datetime": "creazione",
    "Pipeline Stage": "stage",
    "Deal Opportunity Datetime": "opportunity",
    "Deal Signed Won Date": "firma",
    "Deal Bdr Owner Role": "ruolo_bdr",
    "Deal Owner Role": "ruolo_owner",
    "Deal Owner Name": "owner",
    "Deal Amount (MRR)": "mrr",
    "Deal Channel": "canale",
    "Deal Closedate": "closedate",
    "Total Calls": "chiamate",
}


class ErroreFormato(ValueError):
    """L'export non ha la struttura attesa."""


def fix_data(valore: Any, correggi: bool = True):
    """Restituisce una data corretta (pd.Timestamp) oppure NaT.

    - Cella di tipo data: l'export ha giorno e mese invertiti. Se il giorno e' <= 12 si scambiano
      (se e' > 12 non puo' essere stato invertito, quindi resta com'e').
    - Cella di testo gg/mm/aaaa: e' gia' corretta (dayfirst).
    """
    if valore is None or (isinstance(valore, float) and pd.isna(valore)) or valore is pd.NaT:
        return pd.NaT
    if isinstance(valore, (dt.datetime, dt.date, pd.Timestamp)):
        d = pd.Timestamp(valore).normalize()
        if correggi and d.day <= 12:
            try:
                return pd.Timestamp(year=d.year, month=d.day, day=d.month)
            except ValueError:
                return d
        return d
    if isinstance(valore, str):
        m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})", valore)
        if m:
            g, me, a = map(int, m.groups())
            try:
                return pd.Timestamp(year=a, month=me, day=g)
            except ValueError:
                return pd.NaT
    return pd.NaT


def _mese_da_intestazione(v: Any):
    if isinstance(v, (dt.datetime, dt.date, pd.Timestamp)):
        d = pd.Timestamp(v)
        return pd.Timestamp(year=d.year, month=d.month, day=1)
    if isinstance(v, str):
        m = re.match(r"^\s*([a-zA-Z]{3})\w*\s+(\d{4})\s*$", v)
        if m and m.group(1).lower() in MESI_IT:
            return pd.Timestamp(year=int(m.group(2)), month=MESI_IT[m.group(1).lower()], day=1)
    return pd.NaT


def carica_deals(percorso_o_file, config: dict) -> pd.DataFrame:
    try:
        grezzo = pd.read_excel(percorso_o_file, sheet_name="Sales Deals DB", engine="openpyxl")
    except ValueError as e:
        raise ErroreFormato("Foglio 'Sales Deals DB' non trovato nel file.") from e
    mancanti = [c for c in COLONNE if c not in grezzo.columns]
    if mancanti:
        raise ErroreFormato("Colonne mancanti nel foglio 'Sales Deals DB': " + ", ".join(mancanti))
    d = grezzo[list(COLONNE)].rename(columns=COLONNE)
    d = d[d["id"].notna()].copy()
    corr = bool(config.get("correggi_date", True))
    for c in ("creazione", "opportunity", "firma", "closedate"):
        d[c] = d[c].map(lambda v: fix_data(v, corr))
        d[c] = pd.to_datetime(d[c])
    d["mrr"] = pd.to_numeric(d["mrr"], errors="coerce")
    d["chiamate"] = pd.to_numeric(d["chiamate"], errors="coerce")
    d["mese_creazione"] = d["creazione"].dt.to_period("M").dt.to_timestamp()
    d["mese_firma"] = d["firma"].dt.to_period("M").dt.to_timestamp()
    mappa = {k.lower(): v for k, v in config["mappa_canali"].items()}
    d["gruppo_canale"] = d["canale"].fillna("").astype(str).str.strip().str.lower().map(mappa).fillna("Altri canali")
    ruolo = d["ruolo_bdr"].fillna("").astype(str).str.strip()
    ruolo = ruolo.where(ruolo != "", "n.d.")
    d["ruolo_generatore"] = ruolo.replace({"BDR IB MM": "BDR IB"})
    d["stage"] = d["stage"].fillna("").astype(str).str.strip()
    d["ruolo_owner"] = d["ruolo_owner"].fillna("").astype(str).str.strip()
    d["data_giorno_creazione_gt12"] = d["creazione"].dt.day.gt(12)
    return d.reset_index(drop=True)


def carica_costi(percorso_o_file) -> pd.DataFrame:
    """Costi mensili: indice = voce (es. 'Meta Paid'), colonne = primo giorno del mese."""
    try:
        grezzo = pd.read_excel(percorso_o_file, sheet_name="Cost Data", header=None, engine="openpyxl")
    except ValueError as e:
        raise ErroreFormato("Foglio 'Cost Data' non trovato nel file.") from e
    mesi = [_mese_da_intestazione(v) for v in grezzo.iloc[0, 1:]]
    # le intestazioni non riconosciute si ricavano dalla posizione (mese precedente + 1)
    for i, m in enumerate(mesi):
        if pd.isna(m):
            if i > 0 and not pd.isna(mesi[i - 1]):
                mesi[i] = mesi[i - 1] + pd.DateOffset(months=1)
            else:
                for j in range(i + 1, len(mesi)):
                    if not pd.isna(mesi[j]):
                        mesi[i] = mesi[j] - pd.DateOffset(months=j - i)
                        break
    righe = {}
    for _, r in grezzo.iloc[1:].iterrows():
        nome = r.iloc[0]
        if isinstance(nome, str) and nome.strip():
            righe[nome.strip()] = pd.to_numeric(pd.Series(list(r.iloc[1:]), index=mesi), errors="coerce")
    return pd.DataFrame(righe).T


def costo(costi: pd.DataFrame, voce: str, mese: pd.Timestamp) -> float:
    try:
        v = costi.loc[voce, mese]
    except KeyError:
        return 0.0
    return 0.0 if pd.isna(v) else float(v)


def fine_mese(m: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(year=m.year, month=m.month, day=calendar.monthrange(m.year, m.month)[1])
