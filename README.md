# RevOps Monitor

Cruscotto mensile per il CRO: legge l'export Excel del CRM e mostra un **semaforo** con 14 indicatori, il **pacing** del mese, l'andamento degli ultimi 8 mesi, la resa dei lead per ruolo e canale e i controlli sulla qualità dei dati.

Funziona **in locale**: il file Excel non viene inviato a nessun servizio esterno. La logica è in Python (pandas), l'interfaccia è una pagina web in HTML/JavaScript servita dal programma sul tuo computer.

## Requisiti

- Python 3.10 o superiore
- Un browser (Chrome, Edge, Firefox, Safari)

## Installazione

```bash
git clone https://github.com/AlbertoLim98/RevOps.git
cd RevOps
python -m venv .venv
# Windows:  .venv\Scripts\activate      macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

## Uso

```bash
python run.py
```

Si apre il browser su `http://127.0.0.1:8765`.

1. Trascina il file Excel esportato dal CRM (servono i fogli `Sales Deals DB` e `Cost Data`).
2. Scegli il mese in esame e la data di controllo (per un mese chiuso: l'ultimo giorno del mese).
3. Premi **Calcola**. Per ogni indicatore non verde il semaforo dice cosa guardare.

Opzioni: `python run.py --porta 9000` per cambiare porta, `--no-browser` per non aprire il browser.

## Formato dell'export atteso

Foglio `Sales Deals DB`, con queste intestazioni: `Deal ID`, `Deal Creation Datetime`, `Pipeline Stage`, `Deal Opportunity Datetime`, `Deal Signed Won Date`, `Deal Bdr Owner Role`, `Deal Owner Role`, `Deal Owner Name`, `Deal Amount (MRR)`, `Deal Channel`, `Deal Closedate`, `Total Calls`.

Foglio `Cost Data`: prima colonna con le voci (`Sales Cost Details`, `Meta Paid`, `Google Paid`, …), prima riga con i mesi (date oppure testo come `gen 2026`).

Se mancano colonne o fogli, il programma lo segnala con un messaggio.

## Come sono calcolati gli indicatori

- **New MRR**: somma di `Deal Amount (MRR)` dei deal in stage `Won`, per mese di firma.
- **Pacing**: MRR firmato cumulato nel mese contro la media dei 3 mesi precedenti allo stesso giorno.
- **Copertura pipeline**: MRR delle opportunity aperte con closedate nel resto del mese, per il tasso di vittoria stimato, diviso il gap verso il target. Ha senso solo su un export fatto alla data di controllo; altrimenti risulta `N.D.`
- **Quota ultimi 4 giorni**: quota dell'MRR del mese firmata negli ultimi 4 giorni (misura lo slittamento a fine mese).
- **Coorti**: lead → Opportunity e vittorie sulle opportunity chiuse sono calcolati sui deal creati nel mese precedente, che sono ancora in parte aperti: i tassi crescono man mano che si chiudono.
- **Canali**: `Deal Channel` è raggruppato come in `config.json` (Meta paid, Google paid, Altri paid, Outbound e outreach, Altri canali).
- **Ruolo che genera il lead**: `Deal Bdr Owner Role` (`BDR IB MM` è accorpato a `BDR IB`).

### Correzione delle date

L'export contiene date di tipo data con **giorno e mese invertiti** (es. il 9 gennaio compare come 1 settembre). Il programma li scambia se il giorno è ≤ 12; le date in formato testo `gg/mm/aaaa` sono già corrette. Se il CRM viene sistemato alla fonte, disattiva la correzione dall'interfaccia (o con `"correggi_date": false` in `config.json`). Il controllo "date di creazione con giorno > 12" nella scheda Qualità dati segnala quando la correzione non è più necessaria.

## Configurazione

`revops_monitor/config.json` contiene target mensile, tasso di vittoria stimato, mappa dei canali e **soglie del semaforo** (attenzione e allarme per ogni indicatore). Le soglie iniziali derivano dall'analisi di ottobre 2025 – aprile 2026 e vanno calibrate.

## Test

```bash
pytest
# con il file di esempio, anche il controllo sui numeri di aprile 2026:
REVOPS_EXPORT=percorso/export.xlsx pytest        # Windows PowerShell: $env:REVOPS_EXPORT="percorso\export.xlsx"; pytest
```

## Struttura

```
run.py                     avvio del programma
revops_monitor/
  data.py                  lettura e pulizia dell'export
  kpi.py                   calcolo degli indicatori
  server.py                server locale (Flask)
  config.json              target e soglie
  static/                  interfaccia (HTML, CSS, JavaScript, Chart.js)
tests/test_kpi.py          test
```

## Privacy

I file Excel dell'export contengono dati commerciali: `.gitignore` esclude i file `.xlsx` dal repository. Non caricarli su GitHub.
