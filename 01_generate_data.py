"""
Génération d'un jeu de données SIMULÉ pour le projet
« Facturation, commissions et réclamations d'une plateforme de réservation ».

Toutes les données sont fictives (graine fixe => résultats reproductibles).
Scénario : une plateforme de réservation d'hébergements émet des factures et
des relevés pour ses partenaires. Une automatisation du processus de
facturation est mise en production le 2025-03-01 : on veut mesurer son effet
sur les erreurs de facturation, les retards de paiement et les réclamations.

Usage : python python/01_generate_data.py   (depuis la racine du projet)
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)

OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)

START = pd.Timestamp("2024-01-01")  # début de la période d'analyse (factures)
BOOK_START = pd.Timestamp("2023-08-01")  # les réservations démarrent plus tôt : une facture suit le séjour de plusieurs semaines
END = pd.Timestamp("2025-12-31")
GO_LIVE = pd.Timestamp("2025-03-01")  # mise en production de l'automatisation
N_CLIENTS = 1800
N_PARTNERS = 120
N_BOOKINGS = 14500

# ---------------------------------------------------------------- taux de change
fx = pd.DataFrame(
    {"devise": ["CAD", "EUR", "USD"], "taux_vers_cad": [1.00, 1.47, 1.36]}
)

# ---------------------------------------------------------------- partenaires
countries = ["Canada", "France", "Tunisie", "Maroc", "Portugal"]
tax_by_country = {  # taux simplifiés, à but pédagogique uniquement
    "Canada": 0.14975,
    "France": 0.10,
    "Tunisie": 0.07,
    "Maroc": 0.10,
    "Portugal": 0.06,
}
currency_by_country = {
    "Canada": "CAD",
    "France": "EUR",
    "Tunisie": "EUR",
    "Maroc": "EUR",
    "Portugal": "EUR",
}
categories = ["Hôtel", "Riad", "Appartement", "Resort", "Maison d'hôtes"]
partners = pd.DataFrame(
    {
        "partner_id": [f"P{str(i).zfill(3)}" for i in range(1, N_PARTNERS + 1)],
        "nom_partenaire": [f"Partenaire {i}" for i in range(1, N_PARTNERS + 1)],
        "pays": rng.choice(countries, N_PARTNERS, p=[0.30, 0.25, 0.20, 0.15, 0.10]),
        "categorie": rng.choice(categories, N_PARTNERS, p=[0.35, 0.15, 0.25, 0.15, 0.10]),
        "taux_commission": rng.choice([0.10, 0.12, 0.15, 0.18, 0.20], N_PARTNERS),
    }
)
partners["devise"] = partners["pays"].map(currency_by_country)
partners["prix_nuit_base"] = np.round(rng.lognormal(mean=4.7, sigma=0.45, size=N_PARTNERS), 0)

# ---------------------------------------------------------------- clients
segments = ["Particulier", "Agence", "Entreprise"]
client_countries = ["Canada", "France", "États-Unis", "Allemagne", "Tunisie", "Royaume-Uni"]
clients = pd.DataFrame(
    {
        "client_id": [f"C{str(i).zfill(4)}" for i in range(1, N_CLIENTS + 1)],
        "segment": rng.choice(segments, N_CLIENTS, p=[0.70, 0.20, 0.10]),
        "pays_client": rng.choice(
            client_countries, N_CLIENTS, p=[0.35, 0.25, 0.15, 0.10, 0.08, 0.07]
        ),
    }
)
clients["date_inscription"] = START - pd.to_timedelta(
    rng.integers(0, 900, N_CLIENTS), unit="D"
)

# ---------------------------------------------------------------- réservations
# saisonnalité : plus de réservations en été et en décembre
days = pd.date_range(BOOK_START, END, freq="D")
season = np.where(days.month.isin([6, 7, 8]), 1.5, np.where(days.month == 12, 1.3, 1.0))
growth = np.linspace(0.8, 1.3, len(days))  # croissance sur la période
weights = season * growth
weights = weights / weights.sum()
booking_dates = rng.choice(days, N_BOOKINGS, p=weights)

bk = pd.DataFrame(
    {
        "reservation_id": [f"R{str(i).zfill(6)}" for i in range(1, N_BOOKINGS + 1)],
        "client_id": rng.choice(clients["client_id"], N_BOOKINGS),
        "partner_id": rng.choice(partners["partner_id"], N_BOOKINGS),
        "date_reservation": pd.to_datetime(booking_dates),
    }
).sort_values("date_reservation").reset_index(drop=True)
bk["reservation_id"] = [f"R{str(i).zfill(6)}" for i in range(1, N_BOOKINGS + 1)]

bk = bk.merge(
    partners[["partner_id", "prix_nuit_base", "devise"]], on="partner_id", how="left"
)
bk["nuits"] = rng.choice([1, 2, 3, 4, 5, 7, 10], N_BOOKINGS, p=[0.15, 0.25, 0.25, 0.12, 0.10, 0.09, 0.04])
bk["prix_nuit"] = np.round(bk["prix_nuit_base"] * rng.uniform(0.85, 1.25, N_BOOKINGS), 2)
bk["date_sejour"] = bk["date_reservation"] + pd.to_timedelta(rng.integers(5, 90, N_BOOKINGS), unit="D")
bk["montant_ht"] = np.round(bk["prix_nuit"] * bk["nuits"], 2)
bk["statut_reservation"] = rng.choice(
    ["Terminée", "Annulée"], N_BOOKINGS, p=[0.88, 0.12]
)
bk = bk.drop(columns=["prix_nuit_base"])

# ---------------------------------------------------------------- factures
inv = bk[bk["statut_reservation"] == "Terminée"].copy()
inv = inv.merge(
    partners[["partner_id", "pays", "taux_commission"]], on="partner_id", how="left"
)
inv["facture_id"] = [f"F{str(i).zfill(6)}" for i in range(1, len(inv) + 1)]
inv["date_facture"] = inv["date_sejour"] + pd.to_timedelta(
    inv["nuits"].astype(int), unit="D"
) + pd.to_timedelta(rng.integers(1, 6, len(inv)), unit="D")
inv = inv[(inv["date_facture"] >= START) & (inv["date_facture"] <= END)].copy()
inv["facture_id"] = [f"F{str(i).zfill(6)}" for i in range(1, len(inv) + 1)]

after = inv["date_facture"] >= GO_LIVE  # True = processus automatisé

# délai d'émission de la facture après le séjour (jours) : plus rapide après automatisation
inv["delai_emission_jours"] = np.where(
    after,
    np.clip(rng.normal(2, 1, len(inv)), 0, 8),
    np.clip(rng.normal(7, 3, len(inv)), 1, 25),
).round(0).astype(int)

inv["taux_taxe"] = inv["pays"].map(tax_by_country)
inv["montant_taxe"] = np.round(inv["montant_ht"] * inv["taux_taxe"], 2)
inv["montant_ttc"] = np.round(inv["montant_ht"] + inv["montant_taxe"], 2)
inv["commission"] = np.round(inv["montant_ht"] * inv["taux_commission"], 2)

# erreurs de facturation (montant, taxe, doublon...) : 7 % avant, 1,5 % après
p_error = np.where(after, 0.015, 0.07)
inv["erreur_facturation"] = (rng.random(len(inv)) < p_error).astype(int)

# paiement : retard plus fréquent avant l'automatisation et quand erreur
p_late = np.where(after, 0.10, 0.27) + 0.25 * inv["erreur_facturation"]
inv["jours_pour_payer"] = np.clip(rng.normal(22, 8, len(inv)), 3, 60).round(0).astype(int)
late = rng.random(len(inv)) < p_late
inv.loc[late, "jours_pour_payer"] += rng.integers(10, 45, late.sum())
inv["date_echeance"] = inv["date_facture"] + pd.Timedelta(days=30)
inv["date_paiement"] = inv["date_facture"] + pd.to_timedelta(inv["jours_pour_payer"], unit="D")
unpaid = rng.random(len(inv)) < np.where(after, 0.01, 0.03)
inv.loc[unpaid, "date_paiement"] = pd.NaT
# les factures récentes non encore échues sont simplement ouvertes
inv.loc[inv["date_paiement"] > END, "date_paiement"] = pd.NaT
inv["statut_paiement"] = np.select(
    [
        inv["date_paiement"].isna(),
        inv["date_paiement"] > inv["date_echeance"],
    ],
    ["Impayée", "Payée en retard"],
    default="Payée",
)

invoices = inv[
    [
        "facture_id", "reservation_id", "date_facture", "delai_emission_jours",
        "montant_ht", "taux_taxe", "montant_taxe", "montant_ttc", "commission",
        "erreur_facturation", "date_echeance", "date_paiement", "statut_paiement",
    ]
].reset_index(drop=True)

# ---------------------------------------------------------------- réclamations
# probabilité de réclamation : forte si erreur, faible sinon ; plus faible après automatisation
a = inv["date_facture"] >= GO_LIVE
p_claim = np.where(inv["erreur_facturation"] == 1, 0.70, np.where(a, 0.008, 0.03))
has_claim = rng.random(len(inv)) < p_claim
cl = inv.loc[has_claim, ["facture_id", "date_facture", "erreur_facturation"]].copy()
cl["reclamation_id"] = [f"REC{str(i).zfill(5)}" for i in range(1, len(cl) + 1)]
cl["date_reclamation"] = cl["date_facture"] + pd.to_timedelta(rng.integers(1, 20, len(cl)), unit="D")
types_err = ["Erreur de montant", "Taxe incorrecte", "Facture en double", "Commission contestée"]
types_other = ["Relevé manquant", "Question sur le détail", "Autre"]
cl["type_reclamation"] = [
    rng.choice(types_err, p=[0.40, 0.25, 0.15, 0.20]) if e == 1
    else rng.choice(types_other, p=[0.35, 0.45, 0.20])
    for e in cl["erreur_facturation"]
]
res_mean = np.where(cl["date_facture"] >= GO_LIVE, 3.0, 7.5)
cl["delai_resolution_jours"] = np.clip(rng.normal(res_mean, 2.0), 1, 30).round(0).astype(int)
cl["statut_reclamation"] = np.where(
    cl["date_reclamation"] + pd.to_timedelta(cl["delai_resolution_jours"], unit="D") > END,
    "Ouverte", "Résolue",
)
claims = cl[
    ["reclamation_id", "facture_id", "date_reclamation", "type_reclamation",
     "delai_resolution_jours", "statut_reclamation"]
].reset_index(drop=True)

# ---------------------------------------------------------------- défauts de qualité volontaires
# (à nettoyer dans Power Query / pandas : c'est tout l'intérêt de l'exercice)
dirty_clients = clients.copy()
idx = rng.choice(len(dirty_clients), 90, replace=False)
dirty_clients.loc[idx[:30], "pays_client"] = dirty_clients.loc[idx[:30], "pays_client"].str.upper()
dirty_clients.loc[idx[30:60], "pays_client"] = " " + dirty_clients.loc[idx[30:60], "pays_client"] + " "
dirty_clients.loc[idx[60:], "pays_client"] = np.nan

dirty_invoices = invoices.copy()
miss = rng.choice(len(dirty_invoices), 120, replace=False)
dirty_invoices.loc[miss, "taux_taxe"] = np.nan  # taux manquant : à reconstituer
dup = dirty_invoices.sample(60, random_state=SEED)
dirty_invoices = pd.concat([dirty_invoices, dup], ignore_index=True)  # doublons exacts

dirty_claims = pd.concat([claims, claims.sample(15, random_state=SEED)], ignore_index=True)

# ---------------------------------------------------------------- dimension date
dim_date = pd.DataFrame({"date": pd.date_range(START, END, freq="D")})
dim_date["annee"] = dim_date["date"].dt.year
dim_date["mois_num"] = dim_date["date"].dt.month
dim_date["mois"] = dim_date["date"].dt.strftime("%Y-%m")
dim_date["trimestre"] = "T" + dim_date["date"].dt.quarter.astype(str)
dim_date["apres_automatisation"] = np.where(dim_date["date"] >= GO_LIVE, "Après", "Avant")

# ---------------------------------------------------------------- export
def save(df, name):
    df.to_csv(OUT / name, index=False, encoding="utf-8")
    print(f"{name:28s} {len(df):>7,d} lignes")

save(dirty_clients, "clients.csv")
save(partners.drop(columns=["prix_nuit_base"]), "partenaires.csv")
save(bk.drop(columns=["devise"]).merge(partners[["partner_id", "devise"]], on="partner_id"), "reservations.csv")
save(dirty_invoices, "factures.csv")
save(dirty_claims, "reclamations.csv")
save(fx, "taux_change.csv")
save(dim_date, "calendrier.csv")
print("OK - données simulées générées dans", OUT)
