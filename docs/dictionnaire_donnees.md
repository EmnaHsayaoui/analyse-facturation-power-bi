# Dictionnaire de données

Toutes les données sont **simulées** (générées par `python/01_generate_data.py`, graine 42). Les montants sont dans la devise du partenaire (CAD, EUR ou USD) ; la conversion en CAD se fait avec `taux_change.csv`. Les taux de taxe sont simplifiés, à but pédagogique.

## clients.csv (1 800 lignes)
| Colonne | Description |
|---|---|
| client_id | Identifiant client (C0001...) |
| segment | Particulier, Agence ou Entreprise |
| pays_client | Pays du client (⚠ contient des majuscules, des espaces et 30 valeurs vides à nettoyer) |
| date_inscription | Date d'inscription |

## partenaires.csv (120 lignes)
| Colonne | Description |
|---|---|
| partner_id | Identifiant partenaire (P001...) |
| nom_partenaire | Nom fictif |
| pays | Canada, France, Tunisie, Maroc ou Portugal |
| categorie | Hôtel, Riad, Appartement, Resort ou Maison d'hôtes |
| taux_commission | Commission prélevée par la plateforme (10 à 20 %) |
| devise | Devise de facturation du partenaire |

## reservations.csv (14 500 lignes)
| Colonne | Description |
|---|---|
| reservation_id | Identifiant (R000001...) |
| client_id, partner_id | Clés vers clients et partenaires |
| date_reservation, date_sejour | Dates de réservation et de début de séjour |
| nuits, prix_nuit | Durée et prix par nuit (devise du partenaire) |
| montant_ht | nuits × prix_nuit |
| statut_reservation | Terminée ou Annulée (seules les terminées sont facturées) |
| devise | Devise du partenaire |

Les réservations d'août à décembre 2023 existent pour que les factures de début 2024 soient complètes ; elles n'ont pas de facture dans la période d'analyse.

## factures.csv (10 736 lignes dont 60 doublons)
| Colonne | Description |
|---|---|
| facture_id | Identifiant (F000001...) |
| reservation_id | Clé vers reservations |
| date_facture | Date d'émission (période d'analyse : 2024-01-01 à 2025-12-31) |
| delai_emission_jours | Jours entre la fin du séjour et l'émission |
| montant_ht, taux_taxe, montant_taxe, montant_ttc | Montants (⚠ 120 `taux_taxe` manquants) |
| commission | Commission de la plateforme (devise du partenaire) |
| erreur_facturation | 1 si la facture contenait une erreur (montant, taxe, doublon...) |
| date_echeance | date_facture + 30 jours |
| date_paiement | Vide si non payée au 31/12/2025 |
| statut_paiement | Payée, Payée en retard ou Impayée (inclut les factures récentes pas encore échues) |

## reclamations.csv (533 lignes dont 15 doublons)
| Colonne | Description |
|---|---|
| reclamation_id | Identifiant (REC00001...) |
| facture_id | Clé vers factures |
| date_reclamation | Date de la réclamation |
| type_reclamation | Erreur de montant, Taxe incorrecte, Facture en double, Commission contestée, Relevé manquant, Question sur le détail, Autre |
| delai_resolution_jours | Jours pour résoudre |
| statut_reclamation | Résolue ou Ouverte |

## taux_change.csv
Taux de conversion fixes vers le CAD : CAD 1,00 · EUR 1,47 · USD 1,36 (fictifs).

## calendrier.csv (731 lignes)
Table de dates 2024-2025 avec année, mois (AAAA-MM), trimestre et `apres_automatisation` (Avant / Après le 1er mars 2025).

## Scénario intégré aux données
Une automatisation de la facturation entre en service le **1er mars 2025**. Dans les données, après cette date : moins d'erreurs, émission plus rapide, moins de réclamations et de retards de paiement. L'analyse a pour but de le **démontrer avec les données** plutôt que de le supposer.
