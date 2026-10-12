-- ============================================================================
-- Analyse SQL (SQLite) - Facturation, commissions et réclamations
-- Les blocs "-- name: ..." sont exécutés un par un par python/02_run_sql.py
-- Date d'automatisation : 2025-03-01 | Fin de période : 2025-12-31
-- ============================================================================

-- name: 00_vues_nettoyees
-- Nettoyage : suppression des doublons, reconstitution des taux de taxe manquants,
-- normalisation des pays clients, conversion des montants en CAD.
DROP VIEW IF EXISTS v_taux_taxe;
CREATE VIEW v_taux_taxe AS
SELECT 'Canada' AS pays, 0.14975 AS taux UNION ALL
SELECT 'France', 0.10 UNION ALL
SELECT 'Tunisie', 0.07 UNION ALL
SELECT 'Maroc', 0.10 UNION ALL
SELECT 'Portugal', 0.06;

DROP VIEW IF EXISTS v_factures;
CREATE VIEW v_factures AS
WITH dedup AS (
    SELECT DISTINCT * FROM factures
)
SELECT
    d.facture_id,
    d.reservation_id,
    r.client_id,
    r.partner_id,
    p.pays                                            AS pays_partenaire,
    p.categorie,
    d.date_facture,
    strftime('%Y-%m', d.date_facture)                 AS mois,
    CASE WHEN d.date_facture >= '2025-03-01' THEN 'Après' ELSE 'Avant' END AS periode,
    d.delai_emission_jours,
    COALESCE(d.taux_taxe, t.taux)                     AS taux_taxe,
    ROUND(d.montant_ht * x.taux_vers_cad, 2)          AS montant_ht_cad,
    ROUND(d.montant_ht * COALESCE(d.taux_taxe, t.taux) * x.taux_vers_cad, 2) AS taxe_cad,
    ROUND(d.commission * x.taux_vers_cad, 2)          AS commission_cad,
    d.erreur_facturation,
    d.date_echeance,
    d.date_paiement,
    d.statut_paiement
FROM dedup d
JOIN reservations r  ON r.reservation_id = d.reservation_id
JOIN partenaires  p  ON p.partner_id     = r.partner_id
JOIN taux_change  x  ON x.devise         = r.devise
LEFT JOIN v_taux_taxe t ON t.pays        = p.pays;

DROP VIEW IF EXISTS v_reclamations;
CREATE VIEW v_reclamations AS
SELECT DISTINCT * FROM reclamations;

DROP VIEW IF EXISTS v_clients;
CREATE VIEW v_clients AS
SELECT client_id, segment, date_inscription,
       CASE
           WHEN pays_client IS NULL THEN 'Inconnu'
           ELSE CASE UPPER(TRIM(pays_client))
                    WHEN 'ÉTATS-UNIS' THEN 'États-Unis'
                    WHEN 'ROYAUME-UNI' THEN 'Royaume-Uni'
                    ELSE UPPER(SUBSTR(TRIM(pays_client), 1, 1)) || LOWER(SUBSTR(TRIM(pays_client), 2))
                END
       END AS pays_client
FROM clients;

-- name: 01_controle_qualite
-- Combien de problèmes avons-nous corrigés ? (à citer dans le README)
SELECT 'Doublons factures supprimés' AS controle,
       (SELECT COUNT(*) FROM factures) - (SELECT COUNT(*) FROM v_factures) AS valeur
UNION ALL
SELECT 'Taux de taxe reconstitués',
       (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM factures) WHERE taux_taxe IS NULL)
UNION ALL
SELECT 'Doublons réclamations supprimés',
       (SELECT COUNT(*) FROM reclamations) - (SELECT COUNT(*) FROM v_reclamations)
UNION ALL
SELECT 'Clients sans pays', (SELECT COUNT(*) FROM clients WHERE pays_client IS NULL);

-- name: 02_kpi_globaux
SELECT
    COUNT(*)                          AS nb_factures,
    ROUND(SUM(montant_ht_cad), 0)     AS ca_ht_cad,
    ROUND(SUM(commission_cad), 0)     AS commissions_cad,
    ROUND(100.0 * SUM(commission_cad) / SUM(montant_ht_cad), 1) AS taux_commission_moyen_pct
FROM v_factures;

-- name: 03_avant_apres_automatisation
-- Question centrale : l'automatisation a-t-elle amélioré la qualité du processus ?
WITH recl AS (
    SELECT facture_id, MAX(delai_resolution_jours) AS delai_resolution_jours
    FROM v_reclamations GROUP BY facture_id
)
SELECT
    f.periode,
    COUNT(*)                                                          AS nb_factures,
    ROUND(100.0 * AVG(f.erreur_facturation), 2)                       AS taux_erreur_pct,
    ROUND(AVG(f.delai_emission_jours), 1)                             AS delai_emission_moyen_j,
    ROUND(100.0 * COUNT(r.facture_id) / COUNT(*), 2)                  AS taux_reclamation_pct,
    ROUND(AVG(r.delai_resolution_jours), 1)                           AS delai_resolution_moyen_j,
    ROUND(100.0 * SUM(f.statut_paiement = 'Payée en retard') / COUNT(*), 1) AS payees_en_retard_pct
FROM v_factures f
LEFT JOIN recl r ON r.facture_id = f.facture_id
GROUP BY f.periode
ORDER BY CASE f.periode WHEN 'Avant' THEN 0 ELSE 1 END;

-- name: 04_evolution_mensuelle
-- Fonctions de fenêtre : variation vs mois précédent et moyenne mobile 3 mois.
WITH m AS (
    SELECT mois,
           SUM(commission_cad)                       AS commissions,
           100.0 * AVG(erreur_facturation)           AS taux_erreur_pct
    FROM v_factures
    GROUP BY mois
)
SELECT
    mois,
    ROUND(commissions, 0) AS commissions_cad,
    ROUND(100.0 * (commissions - LAG(commissions) OVER (ORDER BY mois))
          / LAG(commissions) OVER (ORDER BY mois), 1)         AS var_vs_mois_prec_pct,
    ROUND(AVG(commissions) OVER (ORDER BY mois ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0) AS moy_mobile_3m,
    ROUND(taux_erreur_pct, 2)                                  AS taux_erreur_pct
FROM m
ORDER BY mois;

-- name: 05_year_over_year_2025_vs_2024
-- Benchmark Year-over-Year par mois civil (hors mois sans équivalent).
WITH m AS (
    SELECT CAST(strftime('%Y', date_facture) AS INT) AS annee,
           CAST(strftime('%m', date_facture) AS INT) AS mois_num,
           SUM(montant_ht_cad) AS ca
    FROM v_factures GROUP BY 1, 2
)
SELECT a.mois_num,
       ROUND(b.ca, 0) AS ca_2024,
       ROUND(a.ca, 0) AS ca_2025,
       ROUND(100.0 * (a.ca - b.ca) / b.ca, 1) AS croissance_yoy_pct
FROM m a
JOIN m b ON b.mois_num = a.mois_num AND b.annee = a.annee - 1
WHERE a.annee = 2025
ORDER BY a.mois_num;

-- name: 06_top_partenaires
-- Les 10 partenaires qui rapportent le plus de commissions, avec leur taux de réclamation.
WITH recl AS (
    SELECT DISTINCT facture_id FROM v_reclamations
),
base AS (
    SELECT f.partner_id, f.pays_partenaire, f.categorie,
           COUNT(*) AS nb_factures,
           SUM(f.commission_cad) AS commissions,
           100.0 * COUNT(r.facture_id) / COUNT(*) AS taux_recl_pct
    FROM v_factures f
    LEFT JOIN recl r ON r.facture_id = f.facture_id
    GROUP BY f.partner_id, f.pays_partenaire, f.categorie
)
SELECT RANK() OVER (ORDER BY commissions DESC) AS rang,
       partner_id, pays_partenaire, categorie, nb_factures,
       ROUND(commissions, 0) AS commissions_cad,
       ROUND(taux_recl_pct, 1) AS taux_reclamation_pct
FROM base
ORDER BY rang
LIMIT 10;

-- name: 07_types_de_reclamations
-- Quelles réclamations ont disparu après l'automatisation ?
-- Les deux périodes n'ont pas la même durée : on compare donc pour 1 000 factures émises.
SELECT r.type_reclamation,
       SUM(f.periode = 'Avant') AS avant,
       SUM(f.periode = 'Après') AS apres,
       ROUND(1000.0 * SUM(f.periode = 'Avant') / (SELECT COUNT(*) FROM v_factures WHERE periode = 'Avant'), 1) AS avant_pour_1000,
       ROUND(1000.0 * SUM(f.periode = 'Après') / (SELECT COUNT(*) FROM v_factures WHERE periode = 'Après'), 1) AS apres_pour_1000
FROM v_reclamations r
JOIN v_factures f ON f.facture_id = r.facture_id
GROUP BY r.type_reclamation
ORDER BY avant_pour_1000 DESC;

-- name: 08_vieillissement_des_impayes
-- Balance âgée au 2025-12-31 des factures non payées (montant TTC en CAD).
SELECT
    CASE
        WHEN julianday('2025-12-31') - julianday(date_echeance) <= 0  THEN '1. Non échue'
        WHEN julianday('2025-12-31') - julianday(date_echeance) <= 30 THEN '2. 1-30 j de retard'
        WHEN julianday('2025-12-31') - julianday(date_echeance) <= 60 THEN '3. 31-60 j de retard'
        ELSE '4. Plus de 60 j de retard'
    END AS tranche,
    COUNT(*) AS nb_factures,
    ROUND(SUM(montant_ht_cad + taxe_cad), 0) AS montant_ttc_cad
FROM v_factures
WHERE statut_paiement = 'Impayée'
GROUP BY tranche
ORDER BY tranche;

-- name: 09_segments_clients
-- Quels segments / pays de clients génèrent le plus de chiffre d'affaires ?
SELECT c.segment, c.pays_client,
       COUNT(*) AS nb_factures,
       ROUND(SUM(f.montant_ht_cad), 0) AS ca_ht_cad
FROM v_factures f
JOIN v_clients c ON c.client_id = f.client_id
GROUP BY c.segment, c.pays_client
ORDER BY ca_ht_cad DESC
LIMIT 10;
