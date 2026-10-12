-- Query per la tabella "comuni" (creata da src/analisi.py in accessibilita.db)
-- Si possono eseguire con DB Browser for SQLite (gratuito).
-- Colonne: reg, "Denominazione Regione", Comune, POPRES21,
--          CLOS_STAZ, CLOS_AUTO, CLOS_AERO, CLOS_PORT (minuti), ripartizione

-- 1) Popolazione e tempo medio ponderato di accesso alla ferrovia, per regione
SELECT "Denominazione Regione" AS regione,
       SUM(POPRES21) AS popolazione,
       ROUND(SUM(POPRES21 * CLOS_STAZ) * 1.0 / SUM(POPRES21), 1) AS minuti_medi_ferrovia
FROM comuni
GROUP BY reg
ORDER BY minuti_medi_ferrovia DESC;

-- 2) Tempi medi ponderati per ripartizione e infrastruttura
SELECT ripartizione,
       ROUND(SUM(POPRES21 * CLOS_STAZ) * 1.0 / SUM(POPRES21), 1) AS ferrovia,
       ROUND(SUM(POPRES21 * CLOS_AUTO) * 1.0 / SUM(POPRES21), 1) AS autostrada,
       ROUND(SUM(POPRES21 * CLOS_AERO) * 1.0 / SUM(POPRES21), 1) AS aeroporto,
       ROUND(SUM(POPRES21 * CLOS_PORT) * 1.0 / SUM(POPRES21), 1) AS porto
FROM comuni
GROUP BY ripartizione;

-- 3) I 10 comuni con più di 5.000 abitanti più lontani da una stazione
SELECT Comune, "Denominazione Regione" AS regione, POPRES21, CLOS_STAZ
FROM comuni
WHERE POPRES21 > 5000
ORDER BY CLOS_STAZ DESC
LIMIT 10;

-- 4) Quota di popolazione a più di 30 minuti da una stazione, per regione
SELECT "Denominazione Regione" AS regione,
       ROUND(100.0 * SUM(CASE WHEN CLOS_STAZ > 30 THEN POPRES21 ELSE 0 END)
             / SUM(POPRES21), 1) AS pct_pop_oltre_30min
FROM comuni
GROUP BY reg
ORDER BY pct_pop_oltre_30min DESC;
