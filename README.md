Facturation, commissions et réclamations : mesurer l'effet d'une automatisation

Projet d'analyse de données de bout en bout (SQL, Python, Power BI) sur une plateforme de réservation d'hébergements.

Auteure : Emna Hsayaoui, analyste de données et Business Analyst (Tunis, Tunisie).

Données 100 % simulées. Elles sont générées par un script reproductible (python/01_generate_data.py, graine 42). L'effet de l'automatisation y est volontairement injecté : l'objectif du projet est de démontrer une méthode d'analyse, pas de présenter un résultat d'entreprise réel.

1. Contexte et question business

Une plateforme de réservation facture ses partenaires (hôtels, riads, appartements) et leur envoie des relevés. Le processus était manuel : erreurs de montant ou de taxe, factures tardives, réclamations, retards de paiement. Le 1er mars 2025, le processus de facturation est automatisé.

Question de la direction : l'automatisation a-t-elle réellement amélioré la qualité de la facturation, les réclamations et l'encaissement, et où reste-t-il de l'argent à récupérer ?

2. Données

7 tables (clients, partenaires, réservations, factures, réclamations, taux de change, calendrier), 10 676 factures sur 2024-2025 dans 3 devises. Description complète dans docs/dictionnaire_donnees.md.

Défauts de qualité volontairement présents : 60 factures en double, 120 taux de taxe manquants, 15 réclamations en double, pays clients mal saisis ou vides (30).

3. Méthode
Nettoyage : suppression des doublons, reconstitution des taux de taxe d'après le pays du partenaire, normalisation des pays, conversion des montants en CAD.
Analyse SQL (sql/analysis.sql, testée sur SQLite) : KPIs, comparaison avant/après, évolution mensuelle (fonctions de fenêtre LAG, moyenne mobile), Year-over-Year, top partenaires (RANK), balance âgée des impayés.
Analyse Python (python/03_analysis.py) : mêmes indicateurs en pandas pour recouper les résultats, tests statistiques de comparaison de proportions, graphiques.
Dashboard Power BI : modèle en étoile et mesures DAX (dax/mesures.dax). Le pas à pas de construction du rapport en 4 pages est dans docs/guide_power_bi.md. Captures du dashboard à venir.

Les résultats SQL et pandas sont identiques (contrôle croisé).

4. Résultats
Indicateur	Avant (jan. 2024 – fév. 2025)	Après (mars – déc. 2025)
Factures émises	5 601	5 075
Factures avec erreur	7,1 %	1,3 %
Délai d'émission moyen	7,0 jours	2,0 jours
Factures avec réclamation	7,7 %	1,7 %
Délai de résolution moyen d'une réclamation	7,5 jours	3,5 jours
Factures payées en retard	36,2 %	19,7 %
Les trois baisses (erreurs, réclamations, retards de paiement) sont statistiquement significatives (test z de comparaison de deux proportions, p < 10⁻⁴⁰).
Environ 291 erreurs de facturation évitées sur la période « Après » par rapport au taux d'avant.
Les réclamations pour erreur de montant et taxe incorrecte sont celles qui baissent le plus (de 20,2 à 3,9 et de 12,9 à 1,4 pour 1 000 factures).
Le chiffre d'affaires HT atteint 6,37 M CAD, les commissions 0,96 M CAD (15,1 %), avec une croissance de +24,5 % de 2025 par rapport à 2024.
À récupérer : 198 factures impayées avec plus de 60 jours de retard, soit environ 122 000 CAD TTC.

Afficher l'image Afficher l'image Afficher l'image

5. Recommandations
Maintenir et étendre l'automatisation : l'effet sur les erreurs est net et durable (taux sous 2,5 % chaque mois depuis mars 2025).
Lancer une campagne de relance sur les 198 factures de plus de 60 jours (~122 k CAD TTC), à traiter par ordre de montant.
Surveiller les partenaires à fort revenu et fort taux de réclamation (par exemple P013 et P035 dans le top 5 des commissions, avec environ 8 % de réclamations) pour protéger la relation commerciale.
Corriger ce qui reste : les erreurs de montant restent le premier motif de réclamation (3,9 pour 1 000 factures), à auditer manuellement.
6. Limites
Données simulées avec l'effet injecté : les tests statistiques confirment ici un effet que j'ai programmé. Dans un cas réel, il faudrait vérifier les autres causes possibles (saisonnalité, changement de clientèle, nouveaux partenaires).
Comparaison avant/après n'est pas une preuve de causalité : sans groupe témoin, d'autres changements simultanés pourraient expliquer une partie de l'écart. Une méthode plus solide serait une analyse de séries temporelles interrompues ou une mise en production progressive.
Les périodes n'ont pas la même durée (14 mois avant, 10 mois après) : on compare donc des taux, jamais des volumes bruts.
« Payée en retard » exclut les factures encore impayées ; les factures récentes pas encore échues sont comptées dans « Impayée ».
7. Reproduire le projet
bash
pip install pandas numpy matplotlib
python python/01_generate_data.py   # génère data/*.csv
python python/02_run_sql.py         # exécute sql/analysis.sql sur SQLite
python python/03_analysis.py        # KPIs, tests, graphiques, data/clean/

Puis suivez docs/guide_power_bi.md pour construire le dashboard.

8. Structure du dépôt
data/            CSV bruts (et clean/ : versions nettoyées)
sql/             analysis.sql
python/          01_generate_data.py, 02_run_sql.py, 03_analysis.py
dax/             mesures.dax
docs/            guide Power BI, dictionnaire de données, résultats, graphiques
