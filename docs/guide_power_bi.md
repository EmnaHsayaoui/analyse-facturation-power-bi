# Guide Power BI : de la donnée brute au dashboard

Durée estimée : 3 à 5 heures. Deux chemins possibles pour le nettoyage :

- **Chemin rapide** : importer les fichiers déjà nettoyés de `data/clean/`. Vous passez directement à l'étape 3.
- **Chemin complet (recommandé)** : importer les CSV bruts de `data/` et faire le nettoyage dans Power Query, comme on le ferait sur des données réelles.

> Le code M et DAX de ce guide n'a pas encore été testé dans Power BI Desktop. Sa logique a été vérifiée par les requêtes SQL et le script pandas (mêmes résultats). À tester et à ajuster si les noms de tables ou de colonnes diffèrent.

## 1. Importer les données

1. Power BI Desktop > **Obtenir les données > Texte/CSV**, importez : `clients.csv`, `partenaires.csv`, `reservations.csv`, `factures.csv`, `reclamations.csv`, `taux_change.csv`, `calendrier.csv`.
2. Cliquez sur **Transformer les données** pour ouvrir Power Query.
3. Créez un paramètre **Dossier** (Gérer les paramètres > Nouveau, type Texte), par exemple `C:\projet\data\`, pour ne pas écrire le chemin en dur.

## 2. Nettoyer dans Power Query

Problèmes volontairement présents dans les données (à corriger) :

| Table | Problème | Correction |
|---|---|---|
| `factures` | 60 lignes en double | `Supprimer les doublons` sur toutes les colonnes |
| `factures` | 120 `taux_taxe` manquants | Reconstituer d'après le pays du partenaire |
| `reclamations` | 15 lignes en double | `Supprimer les doublons` |
| `clients` | Pays en majuscules, avec espaces, ou vides (30) | Nettoyer, puis remplacer les vides par « Inconnu » |

**Clients** : dans l'éditeur avancé de la requête `clients`, ajoutez après la mise en type :

```m
NettoyagePays = Table.TransformColumns(
    Types,
    {{"pays_client", each if _ = null then "Inconnu" else Text.Proper(Text.Trim(_)), type text}}
)
```

**Taux de taxe** : créez via *Saisir des données* une table `TauxTaxe` (colonnes `pays`, `taux_pays`) :
Canada 0,14975 · France 0,10 · Tunisie 0,07 · Maroc 0,10 · Portugal 0,06.

**Factures** (requête complète, à adapter au nom de vos requêtes `Reservations`, `Partenaires`, `TauxChange`, `TauxTaxe`) :

```m
let
    Source = Csv.Document(File.Contents(Dossier & "factures.csv"),
        [Delimiter = ",", Columns = 13, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Entetes = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Types = Table.TransformColumnTypes(Entetes, {
        {"date_facture", type date}, {"date_echeance", type date}, {"date_paiement", type date},
        {"delai_emission_jours", Int64.Type}, {"montant_ht", type number},
        {"taux_taxe", type number}, {"montant_taxe", type number}, {"montant_ttc", type number},
        {"commission", type number}, {"erreur_facturation", Int64.Type}}, "en-US"),
    SansDoublons = Table.Distinct(Types),

    // Réservation : client, partenaire, devise
    JoinRes = Table.NestedJoin(SansDoublons, {"reservation_id"}, Reservations, {"reservation_id"}, "R", JoinKind.LeftOuter),
    ExpRes = Table.ExpandTableColumn(JoinRes, "R", {"client_id", "partner_id", "devise"}),

    // Partenaire : pays et catégorie
    JoinPar = Table.NestedJoin(ExpRes, {"partner_id"}, Partenaires, {"partner_id"}, "P", JoinKind.LeftOuter),
    ExpPar = Table.ExpandTableColumn(JoinPar, "P", {"pays", "categorie"}),

    // Taux de taxe : on garde celui de la facture, sinon celui du pays
    JoinTaxe = Table.NestedJoin(ExpPar, {"pays"}, TauxTaxe, {"pays"}, "T", JoinKind.LeftOuter),
    ExpTaxe = Table.ExpandTableColumn(JoinTaxe, "T", {"taux_pays"}),
    TauxFinal = Table.AddColumn(ExpTaxe, "taux_taxe_final", each [taux_taxe] ?? [taux_pays], type number),

    // Conversion en CAD
    JoinFx = Table.NestedJoin(TauxFinal, {"devise"}, TauxChange, {"devise"}, "X", JoinKind.LeftOuter),
    ExpFx = Table.ExpandTableColumn(JoinFx, "X", {"taux_vers_cad"}),
    MontantCad = Table.AddColumn(ExpFx, "montant_ht_cad", each Number.Round([montant_ht] * [taux_vers_cad], 2), type number),
    TaxeCad = Table.AddColumn(MontantCad, "taxe_cad", each Number.Round([montant_ht] * [taux_taxe_final] * [taux_vers_cad], 2), type number),
    CommCad = Table.AddColumn(TaxeCad, "commission_cad", each Number.Round([commission] * [taux_vers_cad], 2), type number)
in
    CommCad
```

Pour `reclamations`, `reservations`, `partenaires` et `calendrier` : typer les colonnes (dates en type date, montants en nombre décimal) et supprimer les doublons de `reclamations`. La colonne `date` de `calendrier` doit absolument être de type date.

Désactivez le chargement (clic droit > *Activer le chargement* décoché) pour `TauxTaxe`, `TauxChange` et `Reservations` : ce sont des tables intermédiaires.

Cliquez sur **Fermer et appliquer**.

## 3. Modèle de données (schéma en étoile)

Dans la vue *Modèle*, créez ces relations (une vers plusieurs, filtre dans le sens unique) :

```
Calendrier[date]        1 ──► * Factures[date_facture]
Clients[client_id]      1 ──► * Factures[client_id]
Partenaires[partner_id] 1 ──► * Factures[partner_id]
Factures[facture_id]    1 ──► * Reclamations[facture_id]
```

Marquez `Calendrier` comme **table de dates** (Outils de table > Marquer comme table de dates, colonne `date`). Triez `Calendrier[mois]` correctement et masquez les colonnes techniques.

## 4. Mesures DAX

Ouvrez `dax/mesures.dax` : créez une table vide `Mesures` et collez les mesures une par une (Nouvelle mesure). Formatez les pourcentages en `0,0 %` et les montants en `# ##0 $`.

## 5. Les 4 pages du rapport

**Page 1 : Vue d'ensemble**
- Cartes : `CA HT (CAD)`, `Commissions (CAD)`, `Taux Commission`, `Nb Factures`.
- Courbe : `CA HT (CAD)` et `CA HT N-1` par mois (deux séries, légende visible).
- Barres : commissions par pays de partenaire.
- Segments : année, pays partenaire, catégorie.

**Page 2 : Qualité et automatisation (la page qui raconte l'histoire)**
- Cartes : `Taux Erreur Avant Automatisation`, `Taux Erreur Après Automatisation`, `Erreurs Évitées`.
- Courbe : `Taux Erreur` par mois, avec une ligne de référence au 1er mars 2025.
- Barres : `Réclamations pour 1000 Factures` par type, avec `Calendrier[apres_automatisation]` en légende.
- Carte : `Délai Résolution Moyen (j)` avant/après.

**Page 3 : Encaissement**
- Anneau : factures par `statut_paiement`.
- Barres : `Montant Impayé TTC (CAD)` par `Tranche Retard` (à créer comme colonne calculée dans la table `Factures`, le code est en commentaire à la fin de `mesures.dax`).
- Carte : `Taux Paiement en Retard`.

**Page 4 : Partenaires et clients**
- Tableau : top 10 partenaires par `Commissions (CAD)`, avec `Taux Réclamation`.
- Nuage de points : commissions (x) et taux de réclamation (y), un point par partenaire.
- Barres : CA par segment client.

Conseils de mise en forme : une seule couleur d'accent, titres qui énoncent la conclusion (« Les erreurs de facturation ont chuté de 7,1 % à 1,3 % »), pas plus de 6 visuels par page.

## 6. Publier

- Si votre compte le permet, **Fichier > Publier** sur Power BI Service. Sinon, faites simplement une capture d'écran de chaque page et exportez le rapport en PDF (Fichier > Exporter).
- Ajoutez les captures dans le README GitHub et dans un post LinkedIn.
- Gardez toujours le fichier `.pbix` dans votre dépôt (ou un lien de téléchargement).
