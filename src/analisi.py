# -*- coding: utf-8 -*-
"""
Accessibilità alle infrastrutture di trasporto in Italia (dati ISTAT 2021).

Un solo comando esegue tutto il progetto:
    python src/analisi.py

Cosa produce (a partire dal file ISTAT in data/):
  - output/*.csv                  tabelle degli indici (Gini, Kakwani)
  - output/risultati_progetto.xlsx  cartella Excel con tabelle e grafico
  - output/grafici/*.png          grafici per il README
  - accessibilita.db              database SQLite + risultati delle query SQL
  - powerbi/*.csv                 tabelle pronte da importare in Power BI
  - README.md                     sezione "Risultati principali" aggiornata
"""
from pathlib import Path
import re
import sqlite3

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl.chart import BarChart, Reference

BASE = Path(__file__).resolve().parent.parent
FILE_DATI = BASE / "data" / "istat_matrice_indici_accessibilita_2023.xlsx"
OUT = BASE / "output"
GRAF = OUT / "grafici"
PBI = BASE / "powerbi"
DB = BASE / "accessibilita.db"
SQL_FILE = BASE / "sql" / "query.sql"
README = BASE / "README.md"

CLOS = ["CLOS_STAZ", "CLOS_AUTO", "CLOS_AERO", "CLOS_PORT"]
NOMI = {"STAZ": "staz", "AUTO": "auto", "AERO": "aero", "PORT": "port"}
ETICHETTE = {"staz": "Ferrovia", "auto": "Autostrada",
             "aero": "Aeroporto", "port": "Porto"}

NORD = [1, 2, 3, 4, 5, 6, 7, 8]
CENTRO = [9, 10, 11, 12]
SUD = [13, 14, 15, 16, 17, 18, 19, 20]


# ---------------------------------------------------------------- indici
def gini(x):
    """Indice di Gini (formulazione discreta)."""
    x = np.array(x, dtype=float)
    x = x[~np.isnan(x)]
    if x.size == 0 or x.sum() == 0:
        return 0.0
    x = np.sort(x)
    n = len(x)
    i = np.arange(1, n + 1)
    return 2 * np.sum(i * x) / (n * x.sum()) - (n + 1) / n


def ripartizione(cod):
    if cod in NORD:
        return "Nord"
    if cod in CENTRO:
        return "Centro"
    if cod in SUD:
        return "Sud"
    return np.nan


def tabella_indici(g):
    """Gini, Kakwani semplice e normalizzato, medie e mediane per un gruppo."""
    r = {"n_comuni": len(g), "popolazione": g["POPRES21"].sum(),
         "gini_pop": gini(g["POPRES21"])}
    for sigla, nome in NOMI.items():
        r["gini_" + nome] = gini(g["MIN_CLOS_" + sigla])
    for nome in NOMI.values():
        r["kakwani_" + nome] = r["gini_" + nome] - r["gini_pop"]
    den = 1 - r["gini_pop"]
    for nome in NOMI.values():
        r["kakwaniN_" + nome] = r["kakwani_" + nome] / den if den else np.nan
    pop = g["POPRES21"].sum()
    for sigla, nome in NOMI.items():
        r["min_medi_pond_" + nome] = (
            g["MIN_CLOS_" + sigla].sum() / pop if pop else np.nan)
        r["pct_pop_oltre30_" + nome] = (
            100 * g.loc[g["CLOS_" + sigla] > 30, "POPRES21"].sum() / pop
            if pop else np.nan)
    return pd.Series(r)


def indici_per(df, colonna):
    righe = {k: tabella_indici(g) for k, g in df.groupby(colonna)}
    return pd.DataFrame(righe).T


# ----------------------------------------------------------------- dati
def carica_dati(path=FILE_DATI):
    """Legge il foglio 'Accessibilità comuni' del file ufficiale ISTAT."""
    if not path.exists():
        raise SystemExit(f"File non trovato: {path}")
    grezzo = pd.read_excel(path, sheet_name="Accessibilità comuni", header=1)
    # Colonne scelte per posizione (struttura del file ISTAT):
    # 0 codice regione, 1 regione, 10 Procom, 12 comune,
    # 14 popolazione censuaria 2021, 15-18 tempi minimi (stazione,
    # autostrada, aeroporto, porto)
    df = pd.DataFrame({
        "reg": pd.to_numeric(grezzo.iloc[:, 0], errors="coerce"),
        "Denominazione Regione": grezzo.iloc[:, 1],
        "Procom 01.01.2021": grezzo.iloc[:, 10],
        "Comune": grezzo.iloc[:, 12],
        "POPRES21": pd.to_numeric(grezzo.iloc[:, 14], errors="coerce"),
        "CLOS_STAZ": pd.to_numeric(grezzo.iloc[:, 15], errors="coerce"),
        "CLOS_AUTO": pd.to_numeric(grezzo.iloc[:, 16], errors="coerce"),
        "CLOS_AERO": pd.to_numeric(grezzo.iloc[:, 17], errors="coerce"),
        "CLOS_PORT": pd.to_numeric(grezzo.iloc[:, 18], errors="coerce"),
    })
    df = df.dropna(subset=["reg", "POPRES21"])
    df["reg"] = df["reg"].astype(int)
    # Minuti totali = popolazione x tempo minimo di accesso
    for c in CLOS:
        df["MIN_" + c] = df["POPRES21"] * df[c]
    df["ripartizione"] = df["reg"].apply(ripartizione)
    return df


# ------------------------------------------------------------------ SQL
def esegui_sql(df):
    """Crea il database SQLite ed esegue le query di sql/query.sql."""
    risultati = {}
    with sqlite3.connect(DB) as con:
        df.to_sql("comuni", con, if_exists="replace", index=False)
        testo = SQL_FILE.read_text(encoding="utf-8")
        query = [q.strip() for q in testo.split(";") if "SELECT" in q.upper()]
        for i, q in enumerate(query, start=1):
            risultati[f"SQL_{i}"] = pd.read_sql_query(q, con)
    return risultati


# --------------------------------------------------------------- grafici
def grafici(per_rip, per_reg):
    GRAF.mkdir(parents=True, exist_ok=True)
    ordine = [r for r in ["Nord", "Centro", "Sud"] if r in per_rip.index]

    # 1) Kakwani normalizzato per ripartizione
    k = per_rip.loc[ordine, [f"kakwaniN_{n}" for n in NOMI.values()]]
    k.columns = [ETICHETTE[n] for n in NOMI.values()]
    ax = k.plot(kind="bar", figsize=(8, 5))
    ax.set_title("Indice di Kakwani normalizzato per ripartizione")
    ax.set_ylabel("Kakwani normalizzato")
    ax.axhline(0, color="black", linewidth=0.8)
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(GRAF / "kakwani_ripartizioni.png", dpi=150)
    plt.close()

    # 2) Tempo medio ponderato per ripartizione
    t = per_rip.loc[ordine, [f"min_medi_pond_{n}" for n in NOMI.values()]]
    t.columns = [ETICHETTE[n] for n in NOMI.values()]
    ax = t.plot(kind="bar", figsize=(8, 5))
    ax.set_title("Tempo medio ponderato di accesso (minuti)")
    ax.set_ylabel("Minuti")
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(GRAF / "tempi_medi_ripartizioni.png", dpi=150)
    plt.close()

    # 3) Kakwani ferrovia per regione
    r = per_reg.sort_values("kakwaniN_staz")
    plt.figure(figsize=(8, 7))
    plt.barh(r["regione"], r["kakwaniN_staz"])
    plt.title("Kakwani normalizzato - accesso alla ferrovia, per regione")
    plt.xlabel("Kakwani normalizzato")
    plt.tight_layout()
    plt.savefig(GRAF / "kakwani_ferrovia_regioni.png", dpi=150)
    plt.close()


# ----------------------------------------------------------------- Excel
def excel(italia, per_rip, per_reg, sql_ris, df):
    percorso = OUT / "risultati_progetto.xlsx"
    with pd.ExcelWriter(percorso, engine="openpyxl") as w:
        italia.round(4).to_excel(w, sheet_name="Italia")
        per_rip.round(4).to_excel(w, sheet_name="Ripartizioni")
        per_reg.round(4).to_excel(w, sheet_name="Regioni", index=False)
        for nome, tab in sql_ris.items():
            tab.to_excel(w, sheet_name=nome, index=False)
        df.drop(columns=["Procom 01.01.2021"]).to_excel(
            w, sheet_name="Dati_comuni", index=False)

        # Grafico nativo Excel: Kakwani normalizzato per ripartizione
        ws = w.sheets["Ripartizioni"]
        cols = list(per_rip.columns)
        n_righe = len(per_rip)
        ch = BarChart()
        ch.type = "col"
        ch.title = "Kakwani normalizzato per ripartizione"
        ch.y_axis.title = "Kakwani normalizzato"
        for nome in NOMI.values():
            idx = cols.index(f"kakwaniN_{nome}") + 2  # +1 indice, +1 base 1
            ref = Reference(ws, min_col=idx, min_row=1, max_row=n_righe + 1)
            ch.add_data(ref, titles_from_data=True)
        ch.set_categories(Reference(ws, min_col=1, min_row=2,
                                    max_row=n_righe + 1))
        ch.width, ch.height = 20, 10
        ws.add_chart(ch, "A8")


# ---------------------------------------------------------------- README
def md_tabella(df, formato="{:.3f}"):
    righe = ["| " + " | ".join(df.columns) + " |",
             "|" + "|".join(["---"] * len(df.columns)) + "|"]
    for _, r in df.iterrows():
        celle = [formato.format(v) if isinstance(v, (float, np.floating))
                 else str(v) for v in r]
        righe.append("| " + " | ".join(celle) + " |")
    return "\n".join(righe)


def aggiorna_readme(italia, per_rip):
    k = [f"kakwaniN_{n}" for n in NOMI.values()]
    it = italia[k].copy()
    it.columns = [ETICHETTE[n] for n in NOMI.values()]
    it.insert(0, "Gini popolazione", italia["gini_pop"])
    it.index = ["Italia"]
    rip = per_rip.loc[[r for r in ["Nord", "Centro", "Sud"]
                       if r in per_rip.index], k].copy()
    rip.columns = [ETICHETTE[n] for n in NOMI.values()]
    rip.insert(0, "Gini popolazione", per_rip.loc[rip.index, "gini_pop"])
    tab = pd.concat([it, rip]).reset_index().rename(
        columns={"index": "Area"})
    blocco = (
        "<!-- RISULTATI -->\n"
        "**Indice di Kakwani normalizzato** (> 0: costo di accesso più "
        "concentrato della popolazione; < 0: meno concentrato).\n\n"
        + md_tabella(tab) + "\n\n"
        "![Kakwani per ripartizione](output/grafici/kakwani_ripartizioni.png)\n"
        "![Tempi medi](output/grafici/tempi_medi_ripartizioni.png)\n"
        "<!-- /RISULTATI -->")
    testo = README.read_text(encoding="utf-8")
    nuovo = re.sub(r"<!-- RISULTATI -->.*?<!-- /RISULTATI -->", blocco,
                   testo, flags=re.S)
    README.write_text(nuovo, encoding="utf-8")


# ------------------------------------------------------------------ main
def main():
    for cartella in (OUT, PBI):
        cartella.mkdir(exist_ok=True)

    df = carica_dati()
    print("1/6 Dati caricati:", df.shape)

    nomi_reg = (df.drop_duplicates("reg")
                  .set_index("reg")["Denominazione Regione"])
    italia = tabella_indici(df).to_frame("ITALIA").T
    per_rip = indici_per(df, "ripartizione")
    per_reg = indici_per(df, "reg")
    per_reg.insert(0, "regione", per_reg.index.map(nomi_reg))
    per_reg.insert(0, "codice_regione", per_reg.index)
    per_reg = per_reg.reset_index(drop=True)
    print("2/6 Indici calcolati")

    italia.round(4).to_csv(OUT / "indici_italia.csv")
    per_rip.round(4).to_csv(OUT / "indici_ripartizioni.csv")
    per_reg.round(4).to_csv(OUT / "indici_regioni.csv", index=False)

    sql_ris = esegui_sql(df)
    for nome, tab in sql_ris.items():
        tab.to_csv(OUT / f"{nome}.csv", index=False)
    print("3/6 Database SQLite creato e query SQL eseguite")

    grafici(per_rip, per_reg)
    print("4/6 Grafici salvati in output/grafici")

    excel(italia, per_rip, per_reg, sql_ris, df)
    print("5/6 Excel creato: output/risultati_progetto.xlsx")

    # Tabelle per Power BI
    df.drop(columns=["Procom 01.01.2021"]).to_csv(
        PBI / "comuni.csv", index=False, sep=";", decimal=",")
    per_reg.round(4).to_csv(PBI / "regioni.csv", index=False,
                            sep=";", decimal=",")
    per_rip.round(4).rename_axis("ripartizione").reset_index().to_csv(
        PBI / "ripartizioni.csv", index=False, sep=";", decimal=",")
    aggiorna_readme(italia, per_rip)
    print("6/6 File Power BI creati e README aggiornato")

    print("\n== ITALIA ==")
    print(italia.round(4).T)
    print("\n== RIPARTIZIONI ==")
    print(per_rip.round(4).T)


if __name__ == "__main__":
    main()
