"""
Analyse pandas : nettoyage, KPIs avant/après automatisation, tests statistiques
et graphiques pour le README.

Sorties :
  - data/clean/*.csv   : données nettoyées (raccourci si vous ne voulez pas
                         refaire le nettoyage dans Power Query)
  - docs/resultats_python.txt
  - docs/graph_*.png

Usage : python python/03_analysis.py   (depuis la racine du projet)
"""
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA, CLEAN, DOCS = ROOT / "data", ROOT / "data" / "clean", ROOT / "docs"
CLEAN.mkdir(exist_ok=True)
DOCS.mkdir(exist_ok=True)
GO_LIVE = pd.Timestamp("2025-03-01")

# Palette de référence (slots 1 et 2) et encres
BLUE, ORANGE = "#2a78d6", "#eb6834"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False,
})

lines = []


def out(s=""):
    print(s)
    lines.append(s)


# ------------------------------------------------------------------ chargement
fx = pd.read_csv(DATA / "taux_change.csv")
partners = pd.read_csv(DATA / "partenaires.csv")
bookings = pd.read_csv(DATA / "reservations.csv", parse_dates=["date_reservation", "date_sejour"])
clients = pd.read_csv(DATA / "clients.csv", parse_dates=["date_inscription"])
inv_raw = pd.read_csv(DATA / "factures.csv", parse_dates=["date_facture", "date_echeance", "date_paiement"])
cl_raw = pd.read_csv(DATA / "reclamations.csv", parse_dates=["date_reclamation"])

# ------------------------------------------------------------------ nettoyage
tax_by_country = {"Canada": 0.14975, "France": 0.10, "Tunisie": 0.07, "Maroc": 0.10, "Portugal": 0.06}

invoices = inv_raw.drop_duplicates().copy()
claims = cl_raw.drop_duplicates().copy()

invoices = (
    invoices.merge(bookings[["reservation_id", "client_id", "partner_id", "devise"]], on="reservation_id")
    .merge(partners[["partner_id", "pays", "categorie"]], on="partner_id")
    .merge(fx, on="devise")
)
invoices["taux_taxe"] = invoices["taux_taxe"].fillna(invoices["pays"].map(tax_by_country))
for col in ["montant_ht", "commission"]:
    invoices[col + "_cad"] = (invoices[col] * invoices["taux_vers_cad"]).round(2)
invoices["taxe_cad"] = (invoices["montant_ht"] * invoices["taux_taxe"] * invoices["taux_vers_cad"]).round(2)
invoices["periode"] = np.where(invoices["date_facture"] >= GO_LIVE, "Après", "Avant")
invoices["mois"] = invoices["date_facture"].dt.to_period("M").astype(str)
invoices["a_reclamation"] = invoices["facture_id"].isin(claims["facture_id"])
invoices["en_retard"] = invoices["statut_paiement"].eq("Payée en retard")

# clients : normalisation des pays
mapping = {"ÉTATS-UNIS": "États-Unis", "ROYAUME-UNI": "Royaume-Uni"}
c = clients["pays_client"].str.strip()
clients["pays_client"] = c.str.upper().map(mapping).fillna(c.str.capitalize()).fillna("Inconnu")

out("=== CONTRÔLE QUALITÉ ===")
out(f"Doublons de factures supprimés : {len(inv_raw) - len(inv_raw.drop_duplicates())}")
out(f"Doublons de réclamations supprimés : {len(cl_raw) - len(claims)}")
out(f"Taux de taxe reconstitués : {int(inv_raw.drop_duplicates()['taux_taxe'].isna().sum())}")
out(f"Clients sans pays (-> 'Inconnu') : {int((clients['pays_client'] == 'Inconnu').sum())}")

# ------------------------------------------------------------------ KPIs avant / après
g = invoices.groupby("periode")
res = pd.DataFrame({
    "factures": g.size(),
    "taux_erreur_%": g["erreur_facturation"].mean() * 100,
    "delai_emission_j": g["delai_emission_jours"].mean(),
    "taux_reclamation_%": g["a_reclamation"].mean() * 100,
    "payees_en_retard_%": g["en_retard"].mean() * 100,
}).loc[["Avant", "Après"]]
res_claims = claims.merge(invoices[["facture_id", "periode"]], on="facture_id")
res["delai_resolution_j"] = res_claims.groupby("periode")["delai_resolution_jours"].mean()
out("\n=== AVANT / APRÈS AUTOMATISATION (1er mars 2025) ===")
out(res.round(2).to_string())


def two_prop_z(x1, n1, x2, n2):
    """Test z de comparaison de deux proportions (bilatéral). Retourne (z, p)."""
    p1, p2, p = x1 / n1, x2 / n2, (x1 + x2) / (n1 + n2)
    z = (p1 - p2) / math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return z, math.erfc(abs(z) / math.sqrt(2))


out("\n=== TESTS STATISTIQUES (comparaison de deux proportions) ===")
for label, col in [("Erreurs de facturation", "erreur_facturation"),
                   ("Réclamations", "a_reclamation"),
                   ("Paiements en retard", "en_retard")]:
    a = invoices[invoices["periode"] == "Avant"][col].astype(int)
    b = invoices[invoices["periode"] == "Après"][col].astype(int)
    z, p = two_prop_z(a.sum(), len(a), b.sum(), len(b))
    out(f"{label:24s} avant {a.mean()*100:5.2f} % -> après {b.mean()*100:5.2f} %   z = {z:6.2f}   p = {p:.2e}")

# ------------------------------------------------------------------ impact en CAD
nb_apres = int((invoices["periode"] == "Après").sum())
err_avant = res.loc["Avant", "taux_erreur_%"] / 100
err_apres = res.loc["Après", "taux_erreur_%"] / 100
evitees = (err_avant - err_apres) * nb_apres
out(f"\nErreurs de facturation évitées sur la période 'Après' : ~{evitees:.0f} factures "
    f"(sur {nb_apres} factures émises)")

# ------------------------------------------------------------------ graphiques
monthly = invoices.groupby("mois").agg(err=("erreur_facturation", "mean")).reset_index()
monthly["err"] *= 100

# Graphique 1 : taux d'erreur mensuel (une seule série => pas de légende, le titre nomme la série)
fig, ax = plt.subplots(figsize=(9, 4.2))
x = np.arange(len(monthly))
ax.plot(x, monthly["err"], color=BLUE, lw=2, marker="o", ms=5, mfc=BLUE, mec=SURFACE, mew=1.5)
gl = monthly.index[monthly["mois"] == "2025-03"][0]
ax.axvline(gl - 0.5, color=INK2, lw=1, ls=(0, (4, 3)))
ax.text(gl - 0.35, monthly["err"].max() * 0.97, "Automatisation\n(1er mars 2025)", color=INK2, fontsize=9, va="top")
ax.set_xticks(x[::2])
ax.set_xticklabels(monthly["mois"][::2], rotation=45, ha="right")
ax.set_ylabel("Factures avec erreur (%)")
ax.set_ylim(0, monthly["err"].max() * 1.15)
ax.grid(axis="y", color=GRID, lw=0.8)
ax.set_title("Taux d'erreur de facturation par mois", loc="left", color=INK, fontweight="bold")
fig.tight_layout()
fig.savefig(DOCS / "graph_1_taux_erreur_mensuel.png", dpi=150)
plt.close(fig)

# Graphique 2 : 4 KPIs, avant/après (petits multiples, une échelle par graphique)
kpis = [("taux_erreur_%", "Erreurs de facturation (%)"),
        ("taux_reclamation_%", "Factures avec réclamation (%)"),
        ("payees_en_retard_%", "Payées en retard (%)"),
        ("delai_emission_j", "Délai d'émission (jours)")]
fig, axes = plt.subplots(1, 4, figsize=(11, 3.6))
for ax, (col, title) in zip(axes, kpis):
    vals = [res.loc["Avant", col], res.loc["Après", col]]
    bars = ax.bar(["Avant", "Après"], vals, color=[ORANGE, BLUE], width=0.6)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.1f}", ha="center", va="bottom", color=INK, fontsize=10)
    ax.set_title(title, fontsize=9.5, color=INK, loc="left")
    ax.set_ylim(0, max(vals) * 1.2)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
handles = [plt.Rectangle((0, 0), 1, 1, color=ORANGE), plt.Rectangle((0, 0), 1, 1, color=BLUE)]
fig.legend(handles, ["Avant automatisation", "Après automatisation"], loc="lower center",
           ncol=2, frameon=False, labelcolor=INK2)
fig.tight_layout(rect=(0, 0.08, 1, 1))
fig.savefig(DOCS / "graph_2_avant_apres.png", dpi=150)
plt.close(fig)

# Graphique 3 : réclamations pour 1 000 factures, par type et par période
n_per = invoices.groupby("periode").size()
t = res_claims.groupby(["type_reclamation", "periode"]).size().unstack(fill_value=0)
t = t.reindex(columns=["Avant", "Après"], fill_value=0)
rate = t.div(n_per.reindex(["Avant", "Après"]), axis=1) * 1000
rate = rate.sort_values("Avant")
fig, ax = plt.subplots(figsize=(8.5, 4.4))
yy = np.arange(len(rate))
h = 0.36
ax.barh(yy + h / 2, rate["Avant"], height=h, color=ORANGE, label="Avant automatisation")
ax.barh(yy - h / 2, rate["Après"], height=h, color=BLUE, label="Après automatisation")
for i, (a, b) in enumerate(zip(rate["Avant"], rate["Après"])):
    ax.text(a + 0.3, i + h / 2, f"{a:.1f}", va="center", fontsize=9, color=INK)
    ax.text(b + 0.3, i - h / 2, f"{b:.1f}", va="center", fontsize=9, color=INK)
ax.set_yticks(yy)
ax.set_yticklabels(rate.index)
ax.set_xlabel("Réclamations pour 1 000 factures émises")
ax.grid(axis="x", color=GRID, lw=0.8)
ax.set_axisbelow(True)
ax.legend(frameon=False, labelcolor=INK2, loc="lower right")
ax.set_title("Types de réclamations : avant vs après", loc="left", color=INK, fontweight="bold")
fig.tight_layout()
fig.savefig(DOCS / "graph_3_types_reclamations.png", dpi=150)
plt.close(fig)

out("\nRéclamations pour 1 000 factures (par type) :")
out(rate.round(1).sort_values("Avant", ascending=False).to_string())

# ------------------------------------------------------------------ exports nettoyés
invoices_out = invoices.drop(columns=["taux_vers_cad", "devise"]).copy()
invoices_out.to_csv(CLEAN / "factures_propres.csv", index=False)
claims.to_csv(CLEAN / "reclamations_propres.csv", index=False)
clients.to_csv(CLEAN / "clients_propres.csv", index=False)
out(f"\nFichiers propres écrits dans {CLEAN}")

(DOCS / "resultats_python.txt").write_text("\n".join(lines), encoding="utf-8")
