"""Dashboard DPE + Enedis 2023 · Dash + Plotly.
Lancer : python app.py  →  http://127.0.0.1:8050
"""
from pathlib import Path
import json
import urllib.request
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State
from dash.exceptions import PreventUpdate

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
DOSSIER = Path(__file__).resolve().parent
ANNEE = 2023
CLASSES = list("ABCDEFG")
COULEUR_DPE = "#246BB0"
COULEUR_ENEDIS = "#E59842"
COULEUR_TEXTE = "#273A50"
COULEUR_FOND = "#F6F8FB"
COULEUR_ALERTE = "#D62828"

ENERGIES_EXCLUES = ["Fioul domestique",
                    "Bois – Bûches",
                    "Bois – Granulés (pellets) ou briquettes"]

# Énergies conservées dans le graphique « Comparaison par énergie principale »
ENERGIES_AFFICHEES = ["Électricité", "Gaz / GPL"]

GEOJSON_URL = ("https://raw.githubusercontent.com/gregoiredavid/france-geojson/"
               "master/departements-version-simplifiee.geojson")
GEOJSON_LOCAL = DOSSIER / "departements.geojson"


# ---------------------------------------------------------------------------
# GeoJSON
# ---------------------------------------------------------------------------
def charger_geojson():
    if GEOJSON_LOCAL.exists():
        try:
            return json.loads(GEOJSON_LOCAL.read_text(encoding="utf-8"))
        except Exception:
            pass
    try:
        req = urllib.request.Request(GEOJSON_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
            GEOJSON_LOCAL.write_text(json.dumps(data), encoding="utf-8")
            return data
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Données
# ---------------------------------------------------------------------------
def charger_donnees():
    chemin = DOSSIER / "dataset_final_2023.csv"
    if not chemin.exists():
        raise FileNotFoundError("dataset_final_2023.csv introuvable.")
    d = pd.read_csv(chemin, encoding="utf-8",
                    dtype={"code_postal": str, "code_commune": str,
                           "departement": str, "id_dpe": str})
    for c in ["conso_enedis_synthetique", "donnee_imputee", "tout_electrique",
              "modifie_apres_2023", "bilan_ef_incoherent", "coordonnees_fiables"]:
        if c in d:
            d[c] = d[c].astype(str).str.lower().isin(["true", "1", "oui"])
    d = d.loc[pd.to_numeric(d.annee, errors="coerce").eq(ANNEE)].copy()
    if "date_dpe" in d:
        d = d.loc[pd.to_datetime(d.date_dpe, errors="coerce").dt.year.eq(ANNEE)].copy()
    for c in ["surface_m2", "conso_dpe_kwh", "conso_enedis_kwh"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    valide = np.isfinite(d[["surface_m2", "conso_dpe_kwh", "conso_enedis_kwh"]]).all(axis=1)
    valide &= d[["surface_m2", "conso_dpe_kwh", "conso_enedis_kwh"]].gt(0).all(axis=1)
    d = d.loc[valide].copy()
    d = d.loc[~d.energie.isin(ENERGIES_EXCLUES)].copy()
    d["dept_code"] = d.departement.astype(str).str.zfill(2)
    if "methode_rapprochement" not in d.columns:
        d["methode_rapprochement"] = ""
    return d


D = charger_donnees()
GEOJSON = charger_geojson()
if GEOJSON is None:
    raise SystemExit("Impossible de charger le GeoJSON des départements.")

NOMS_DEPT = {str(f["properties"]["code"]).zfill(2): f["properties"].get("nom", "")
             for f in GEOJSON["features"]}
TOUS_DEPT = sorted(NOMS_DEPT.keys())


# ---------------------------------------------------------------------------
# Traitement
# ---------------------------------------------------------------------------
def filtrer(d, depts, communes, dpes, energies, surface, elec, exact, bilan):
    q = d.copy()
    if depts: q = q.loc[q.departement.isin(depts)]
    if communes: q = q.loc[q.commune.isin(communes)]
    if dpes: q = q.loc[q.etiquette_dpe.isin(dpes)]
    if energies: q = q.loc[q.energie.isin(energies)]
    q = q.loc[q.surface_m2.between(surface[0], surface[1])]
    if elec: q = q.loc[q.tout_electrique]
    if exact:
        q = q.loc[~q.methode_rapprochement.fillna("").str.startswith("approximatif")]
    if bilan: q = q.loc[~q.bilan_ef_incoherent]
    return q.copy()


def valeur_unique(s):
    return s.iloc[0] if s.nunique() == 1 else "Mixte"


def agreger(d):
    if d.empty:
        return pd.DataFrame(columns=["groupe_adresse", "nb_dpe", "adresse",
                                     "commune", "departement", "dept_code",
                                     "etiquette_dpe", "energie", "surface_m2",
                                     "conso_dpe_kwh", "conso_enedis_kwh",
                                     "origine_enedis", "ecart_kwh",
                                     "ecart_pourcentage"])
    t = d.groupby("groupe_adresse", as_index=False).agg(
        nb_dpe=("id_dpe", "size"), adresse=("adresse", "first"),
        commune=("commune", "first"), departement=("departement", "first"),
        dept_code=("dept_code", "first"),
        etiquette_dpe=("etiquette_dpe", valeur_unique),
        energie=("energie", valeur_unique),
        surface_m2=("surface_m2", "mean"),
        conso_dpe_kwh=("conso_dpe_kwh", "mean"),
        conso_enedis_kwh=("conso_enedis_kwh", "first"),
        origine_enedis=("origine_enedis", "first"))
    t["ecart_kwh"] = t.conso_enedis_kwh - t.conso_dpe_kwh
    t["ecart_pourcentage"] = 100 * t.ecart_kwh / t.conso_dpe_kwh
    return t


def compute_kpis(q, t):
    if t.empty:
        return dict(logements=0, dpe=0, enedis=0, ecart=0, ecart_type=0)
    return dict(logements=len(q), dpe=t.conso_dpe_kwh.mean(),
                enedis=t.conso_enedis_kwh.mean(),
                ecart=t.ecart_kwh.mean(), ecart_type=t.ecart_kwh.std())


def fmt(x, dec=0):
    if pd.isna(x): return "—"
    return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")


def lire_filtres(depts, communes, dpes, energies, surface, options):
    options = options or []
    surf = (surface[0], surface[1]) if surface else \
           (int(D.surface_m2.min()), int(D.surface_m2.max()))
    q = filtrer(D, depts or [], communes or [], dpes or [], energies or [],
                surf, "elec" in options, "exact" in options, "bilan" in options)
    t = agreger(q)
    k = compute_kpis(q, t)
    return q, t, k


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def fig_vide(titre="Aucune donnée"):
    f = go.Figure()
    f.update_layout(height=460, template="plotly_white", title=titre,
                    font=dict(family="Arial", size=12, color=COULEUR_TEXTE))
    return f


def fig_carte(t, stat, dept_selection, mode_selection="click"):
    """Carte à l'échelle de la France entière, avec sélection MULTIPLE."""
    dept_selection = dept_selection or []

    if not t.empty:
        stats = t.groupby("dept_code", as_index=False).agg(
            ecart_moyen=("ecart_kwh", "mean"),
            ecart_type=("ecart_kwh", "std"),
            adresses=("groupe_adresse", "size"))
        stats["ecart_type"] = stats.ecart_type.fillna(0)
        stats["nom_dept"] = stats.dept_code.map(NOMS_DEPT).fillna(stats.dept_code)
    else:
        stats = pd.DataFrame(columns=["dept_code", "ecart_moyen",
                                       "ecart_type", "adresses", "nom_dept"])

    titres = {"ecart_type": "Écart type (kWh)",
              "ecart_moyen": "Écart moyen (kWh)",
              "adresses": "Nombre d'adresses"}
    echelles = {"ecart_type": "RdYlGn_r",
                "ecart_moyen": "RdYlGn_r",
                "adresses": "Blues"}

    if not stats.empty and stats[stat].notna().any():
        vmin = float(stats[stat].min())
        vmax = float(stats[stat].max())
        if vmin == vmax:
            vmax = vmin + 1
    else:
        vmin, vmax = 0, 1

    fig = go.Figure()

    # --- Trace 1 : fond gris pour tous les départements ---
    fig.add_trace(go.Choropleth(
        geojson=GEOJSON,
        locations=TOUS_DEPT,
        featureidkey="properties.code",
        z=[0] * len(TOUS_DEPT),
        colorscale=[[0, "#D8DEE6"], [1, "#D8DEE6"]],
        showscale=False,
        marker=dict(line=dict(color="white", width=0.8)),
        hoverinfo="skip",
        name="Sans données",
    ))

    # --- Trace 2 : départements colorés ---
    if dept_selection:
        stats_show = stats[stats.dept_code.isin(dept_selection)]
    else:
        stats_show = stats

    if not stats_show.empty:
        fig.add_trace(go.Choropleth(
            geojson=GEOJSON,
            locations=stats_show["dept_code"],
            featureidkey="properties.code",
            z=stats_show[stat],
            zmin=vmin, zmax=vmax,
            colorscale=echelles[stat],
            marker=dict(line=dict(color="white", width=0.8)),
            colorbar=dict(
                title=dict(text=titres[stat], side="bottom",
                           font=dict(size=12, color=COULEUR_TEXTE)),
                thickness=14, len=0.55, x=0.02, y=0.02,
                xanchor="left", yanchor="bottom",
                ticks="outside", tickfont=dict(size=11, color=COULEUR_TEXTE),
                bgcolor="rgba(255,255,255,0.85)", outlinewidth=0,
            ),
            customdata=stats_show[["nom_dept", "ecart_moyen", "ecart_type",
                                    "adresses"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Écart moyen : %{customdata[1]:.0f} kWh<br>"
                "Écart type : %{customdata[2]:.0f} kWh<br>"
                "Adresses : %{customdata[3]}<br>"
                "<extra></extra>"
            ),
            name="Données",
        ))

    # --- Trace 3 : contour rouge sur les départements sélectionnés ---
    if dept_selection:
        geo_sel = {"type": "FeatureCollection",
                   "features": [f for f in GEOJSON["features"]
                                if str(f["properties"]["code"]).zfill(2)
                                in dept_selection]}
        if geo_sel["features"]:
            fig.add_trace(go.Choropleth(
                geojson=geo_sel,
                locations=dept_selection,
                featureidkey="properties.code",
                z=[0] * len(dept_selection), showscale=False,
                colorscale=[[0, "rgba(214,40,40,0.20)"],
                            [1, "rgba(214,40,40,0.20)"]],
                marker=dict(line=dict(color=COULEUR_ALERTE, width=3.5)),
                hoverinfo="skip",
                name="Sélection",
            ))

    # --- Cadrage fixe France métropolitaine + Corse ---
    fig.update_geos(
        visible=False,
        showland=False, showocean=False, showcoastlines=False,
        showcountries=False, showframe=False, showlakes=False,
        projection_type="mercator",
        lataxis_range=[41.0, 51.5],
        lonaxis_range=[-5.5, 9.8],
    )

    drag = "select" if mode_selection == "box" else False

    fig.update_layout(
        height=460,
        margin=dict(l=0, r=0, t=0, b=0),
        template="plotly_white",
        font=dict(family="Arial", size=12, color=COULEUR_TEXTE),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        dragmode=drag,
        uirevision="carte-fixe",
        selectdirection="any",
    )
    return fig


def fig_comparison(t, champ, titre, horizontal=False):
    if t.empty:
        return fig_vide(titre)

    # Pour le graphique énergie : ne garder QUE Électricité et Gaz / GPL
    if champ == "energie":
        t = t[t.energie.isin(ENERGIES_AFFICHEES)]
        if t.empty:
            return fig_vide(titre)

    resume = t.groupby(champ, as_index=False).agg(
        DPE=("conso_dpe_kwh", "mean"), Enedis=("conso_enedis_kwh", "mean"),
        Adresses=("groupe_adresse", "size"))
    if champ == "etiquette_dpe":
        resume[champ] = pd.Categorical(resume[champ], CLASSES, ordered=True)
        resume = resume.sort_values(champ)
    else:
        resume = resume.sort_values("Enedis")
    long = resume.melt(id_vars=[champ, "Adresses"], value_vars=["DPE", "Enedis"],
                       var_name="Source", value_name="kWh")
    long["Source"] = long.Source.map({"DPE": "DPE électrique",
                                      "Enedis": "Enedis / simulation"})
    fig = px.bar(long, x="kWh" if horizontal else champ,
                 y=champ if horizontal else "kWh",
                 color="Source", barmode="group",
                 orientation="h" if horizontal else "v",
                 hover_data=["Adresses"],
                 color_discrete_map={"DPE électrique": COULEUR_DPE,
                                     "Enedis / simulation": COULEUR_ENEDIS},
                 title=titre,
                 category_orders={champ: CLASSES} if champ == "etiquette_dpe" else {})
    fig.update_layout(
        height=290, template="plotly_white",
        font=dict(family="Arial", size=12, color=COULEUR_TEXTE),
        title=dict(font=dict(size=15), x=0),
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=-0.25, x=0, title=""),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#E8EDF2", zerolinecolor="#B5C0CC")
    return fig


def carte_metric(titre, valeur):
    return html.Div([
        html.Div(titre, style={"fontSize": "0.78rem", "color": "#66758A",
                               "marginBottom": "4px"}),
        html.Div(valeur, style={"fontSize": "1.35rem", "color": "#153859",
                                "fontWeight": "600"})
    ], style={"background": "white", "border": "1px solid #E2E9F0",
              "borderRadius": "12px", "padding": "10px 14px",
              "minHeight": "70px", "flex": "1"})


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = Dash(__name__, suppress_callback_exceptions=True,
           title="Habitat 2023 · DPE & Enedis")

app.index_string = """
<!DOCTYPE html>
<html>
<head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <style>
    html, body { margin:0; padding:0; background:#F6F8FB;
                 font-family: Arial, sans-serif; color:#273A50; }
    .conteneur { display:flex; height:100vh; overflow:hidden; }
    .sidebar { background:#FFFFFF; border-right:1px solid #E4EAF1;
               flex-shrink:0; transition: width 0.25s ease, padding 0.25s ease;
               box-sizing:border-box; overflow-y:auto; }
    .sidebar.ouvert { width:330px; padding:18px; }
    .sidebar.ferme { width:0; padding:0; overflow:hidden; border-right:none; }
    .principal { flex:1; padding:0; overflow-y:auto; box-sizing:border-box;
                 background:#F6F8FB; }
    .header { padding:14px 24px 8px 24px; display:flex; align-items:center;
              gap:16px; background:#F6F8FB; position:sticky; top:0; z-index:10; }
    .header h1 { font-size:1.5rem; margin:0; color:#153859; }
    .btn-toggle { background:#153859; color:white; border:none;
                  padding:8px 14px; border-radius:10px; cursor:pointer;
                  font-size:0.9rem; font-weight:600; flex-shrink:0;
                  transition: background 0.15s ease; }
    .btn-toggle:hover { background:#205F79; }
    .contenu { padding:8px 24px 24px 24px; }
    h2 { font-size:1.05rem; margin:0 0 4px 0; color:#153859; }
    h4 { font-size:0.78rem; margin:14px 0 4px 0; color:#66758A;
         text-transform:uppercase; letter-spacing:0.7px; font-weight:700; }
    label { font-size:0.82rem; color:#273A50; }
    .bloc-ligne { display:flex; gap:14px; align-items:stretch; }
    .panneau { background:white; border:1px solid #E4EAF1;
               border-radius:12px; padding:14px; }
    .btn-retour { background:#D62828; color:white; border:none;
                  padding:6px 12px; border-radius:8px; cursor:pointer;
                  font-size:0.85rem; margin-bottom:10px; }
    .titre-carte { font-size:0.95rem; font-weight:600; color:#153859;
                   margin:4px 0 8px 4px; }
    .titre-carte span { font-weight:400; color:#66758A; font-size:0.85rem;
                        margin-left:6px; }
    .sous-titre-menu { font-size:0.78rem; color:#66758A; margin-bottom:10px;
                       line-height:1.4; }
    .aide-selection { font-size:0.78rem; color:#153859; background:#EEF3F9;
                      border-radius:8px; padding:6px 10px; margin-bottom:8px;
                      line-height:1.4; }
    .aide-selection b { color:#D62828; }
    </style>
</head>
<body>
    {%app_entry%}
    <footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>
"""

app.layout = html.Div(className="conteneur", children=[
    # ------------------- SIDEBAR -------------------
    html.Div(id="sidebar-wrap", className="sidebar ouvert", children=[
        html.H2("🔍 Recherche & filtres"),
        html.Div("Choisissez un département, une commune, une classe DPE "
                 "ou une énergie pour affiner l'analyse.",
                 className="sous-titre-menu"),

        html.H4("Affichage"),
        dcc.Checklist(
            id="aff-blocs",
            options=[
                {"label": "KPI", "value": "kpi"},
                {"label": "Carte", "value": "carte"},
                {"label": "Graphique classes DPE", "value": "classes"},
                {"label": "Graphique énergie", "value": "energie"},
                {"label": "Téléchargements", "value": "export"},
            ],
            value=["kpi", "carte", "classes", "energie"],
            style={"fontSize": "0.85rem", "lineHeight": "1.7"}),

        html.Hr(style={"margin": "14px 0"}),
        html.H4("Mode de sélection carte"),
        dcc.RadioItems(
            id="mode-selection",
            options=[
                {"label": " Clic simple (1 par 1)", "value": "click"},
                {"label": " Rectangle (plusieurs d'un coup)", "value": "box"},
            ],
            value="click",
            style={"fontSize": "0.82rem", "lineHeight": "1.8"}),
        html.Div(id="aide-mode", className="aide-selection"),

        html.Hr(style={"margin": "14px 0"}),
        html.H4("Filtres de recherche"),

        html.Label("Département"),
        dcc.Dropdown(id="f-dept", multi=True,
                     options=[{"label": f"{v} · {NOMS_DEPT.get(v, '')}", "value": v}
                              for v in sorted(D.departement.dropna().unique())],
                     placeholder="Tous"),

        html.Label("Commune", style={"marginTop": "10px", "display": "block"}),
        dcc.Dropdown(id="f-commune", multi=True,
                     options=[{"label": v, "value": v}
                              for v in sorted(D.commune.dropna().unique())],
                     placeholder="Toutes"),

        html.Label("Classe DPE", style={"marginTop": "10px", "display": "block"}),
        dcc.Dropdown(id="f-dpe", multi=True,
                     options=[{"label": v, "value": v}
                              for v in sorted(D.etiquette_dpe.dropna().unique())],
                     placeholder="Toutes"),

        html.Label("Énergie principale", style={"marginTop": "10px", "display": "block"}),
        dcc.Dropdown(id="f-energie", multi=True,
                     options=[{"label": v, "value": v}
                              for v in sorted(D.energie.dropna().unique())],
                     placeholder="Toutes"),

        html.Label("Surface (m²)", style={"marginTop": "12px", "display": "block"}),
        dcc.RangeSlider(
            id="f-surface",
            min=int(np.floor(D.surface_m2.min())),
            max=int(np.ceil(D.surface_m2.max())),
            value=[int(np.floor(D.surface_m2.min())),
                   int(np.ceil(D.surface_m2.max()))],
            marks=None, tooltip={"placement": "bottom"}),

        html.Div(style={"marginTop": "12px"}, children=[
            dcc.Checklist(
                id="f-options",
                options=[
                    {"label": "Tout électrique", "value": "elec"},
                    {"label": "Écarter rapprochements approximatifs", "value": "exact"},
                    {"label": "Écarter bilans EF signalés", "value": "bilan"},
                ],
                value=[],
                style={"fontSize": "0.8rem", "lineHeight": "1.8"})]),
    ]),

    # ------------------- PRINCIPAL -------------------
    html.Div(className="principal", children=[
        html.Div(className="header", children=[
            html.Button("☰ Menu", id="btn-toggle", className="btn-toggle",
                        n_clicks=0),
            html.H1("Habitat & énergie · 2023"),
        ]),

        html.Div(className="contenu", children=[
            # ---- KPI ----
            html.Div(id="bloc-kpi", style={"marginBottom": "14px"}, children=[
                html.Div(className="bloc-ligne", children=[
                    html.Div(id="kpi-1", style={"flex": "1"}),
                    html.Div(id="kpi-2", style={"flex": "1"}),
                    html.Div(id="kpi-3", style={"flex": "1"}),
                    html.Div(id="kpi-4", style={"flex": "1"}),
                ])
            ]),

            # ---- LIGNE UNIQUE : CARTE + PANNEAU (gauche) | GRAPHIQUES (droite) ----
            html.Div(className="bloc-ligne", style={"marginBottom": "14px"},
                     children=[
                # ---------- COLONNE GAUCHE ----------
                html.Div(style={"flex": "3", "minWidth": "0"}, children=[
                    # Carte
                    html.Div(id="bloc-carte", children=[
                        html.Div(className="titre-carte",
                                 children=["Carte des écarts DPE ↔ Enedis "
                                           "par département"]),
                        html.Div(style={"background": "white",
                                        "border": "1px solid #E4EAF1",
                                        "borderRadius": "12px",
                                        "padding": "8px"}, children=[
                            dcc.RadioItems(
                                id="stat-carte",
                                options=[
                                    {"label": "Écart type", "value": "ecart_type"},
                                    {"label": "Écart moyen", "value": "ecart_moyen"},
                                    {"label": "Nombre d'adresses", "value": "adresses"},
                                ],
                                value="ecart_type",
                                inline=True,
                                style={"fontSize": "0.85rem",
                                       "marginBottom": "4px"}),
                            dcc.Graph(id="carte-dept",
                                      config={"displaylogo": False,
                                              "scrollZoom": False},
                                      style={"height": "460px"}),
                        ]),
                    ]),
                    # Panneau détail sous la carte
                    html.Div(className="panneau",
                             style={"marginTop": "10px"}, children=[
                        html.Button("← Retour à la France",
                                    id="btn-retour",
                                    className="btn-retour",
                                    n_clicks=0,
                                    style={"display": "none"}),
                        html.Div(id="panneau-contenu"),
                    ]),
                ]),

                # ---------- COLONNE DROITE ----------
                html.Div(style={"flex": "2", "minWidth": "0"}, children=[
                    # Graphique classes (haut)
                    html.Div(id="wrap-classes",
                             style={"background": "white",
                                    "border": "1px solid #E4EAF1",
                                    "borderRadius": "12px",
                                    "padding": "8px",
                                    "marginBottom": "10px",
                                    "display": "block"},
                             children=[
                                 dcc.Graph(id="graph-classes",
                                           config={"displaylogo": False},
                                           style={"height": "290px"})]),
                    # Graphique énergie (bas)
                    html.Div(id="wrap-energie",
                             style={"background": "white",
                                    "border": "1px solid #E4EAF1",
                                    "borderRadius": "12px",
                                    "padding": "8px",
                                    "display": "block"},
                             children=[
                                 dcc.Graph(id="graph-energie",
                                           config={"displaylogo": False},
                                           style={"height": "290px"})]),
                ]),
            ]),

            # ---- EXPORTS ----
            html.Div(id="bloc-export", style={"marginBottom": "14px"}, children=[
                html.Div(className="bloc-ligne", children=[
                    html.Button("Télécharger les comparaisons (CSV)",
                                id="btn-download",
                                style={"background": COULEUR_DPE, "color": "white",
                                       "border": "none", "padding": "8px 14px",
                                       "borderRadius": "8px", "cursor": "pointer"}),
                    dcc.Download(id="download-data"),
                ])
            ]),
        ]),
    ]),

    # ---- STORES ----
    dcc.Store(id="dept-store", data=[]),
    dcc.Store(id="sidebar-open", data=True),
])


# ---------------------------------------------------------------------------
# CALLBACKS
# ---------------------------------------------------------------------------

# 0) Toggle sidebar
@app.callback(
    Output("sidebar-open", "data"),
    Input("btn-toggle", "n_clicks"),
    State("sidebar-open", "data"),
    prevent_initial_call=True)
def toggle_sidebar(n, open_):
    if not n:
        raise PreventUpdate
    return not open_


@app.callback(
    Output("sidebar-wrap", "className"),
    Output("btn-toggle", "children"),
    Input("sidebar-open", "data"))
def appliquer_toggle(open_):
    if open_:
        return "sidebar ouvert", "✕ Fermer"
    return "sidebar ferme", "☰ Menu"


# 0bis) Aide contextuelle selon le mode
@app.callback(
    Output("aide-mode", "children"),
    Input("mode-selection", "value"))
def maj_aide(mode):
    if mode == "box":
        return [html.B("Rectangle"), " — maintiens le clic et dessine "
                "un rectangle sur la carte pour sélectionner plusieurs "
                "départements d'un coup."]
    return [html.B("Clic simple"), " — clique sur un département pour "
            "l'ajouter ou le retirer de la sélection."]


# 1a) Clic simple → toggle (actif seulement en mode "click")
@app.callback(
    Output("dept-store", "data", allow_duplicate=True),
    Input("carte-dept", "clickData"),
    State("dept-store", "data"),
    State("mode-selection", "value"),
    prevent_initial_call=True)
def maj_dept_click(clickData, selection, mode):
    if mode != "click":
        raise PreventUpdate
    selection = list(selection or [])
    if not clickData:
        raise PreventUpdate
    points = clickData.get("points") or []
    if not points:
        raise PreventUpdate
    loc = points[0].get("location")
    if not loc:
        raise PreventUpdate
    loc = str(loc).zfill(2)
    if loc in selection:
        selection.remove(loc)
    else:
        selection.append(loc)
    return selection


# 1b) Sélection rectangle → AJOUTE tous les départements de la boîte
@app.callback(
    Output("dept-store", "data", allow_duplicate=True),
    Input("carte-dept", "selectedData"),
    State("dept-store", "data"),
    State("mode-selection", "value"),
    prevent_initial_call=True)
def maj_dept_box(selectedData, selection, mode):
    if mode != "box":
        raise PreventUpdate
    selection = list(selection or [])
    if not selectedData:
        raise PreventUpdate
    points = selectedData.get("points") or []
    nouveaux = []
    for p in points:
        loc = p.get("location")
        if loc:
            loc = str(loc).zfill(2)
            if loc not in selection and loc not in nouveaux:
                nouveaux.append(loc)
    if not nouveaux:
        raise PreventUpdate
    return selection + nouveaux


# 2) Bouton retour → vide la sélection
@app.callback(
    Output("dept-store", "data", allow_duplicate=True),
    Input("btn-retour", "n_clicks"),
    prevent_initial_call=True)
def retour_france(n):
    if not n:
        raise PreventUpdate
    return []


# 3) Visibilité bouton retour
@app.callback(
    Output("btn-retour", "style"),
    Input("dept-store", "data"))
def maj_btn_retour(selection):
    base = {"background": COULEUR_ALERTE, "color": "white", "border": "none",
            "padding": "6px 12px", "borderRadius": "8px", "cursor": "pointer",
            "fontSize": "0.85rem", "marginBottom": "10px"}
    base["display"] = "inline-block" if selection else "none"
    return base


# 4) Carte
@app.callback(
    Output("carte-dept", "figure"),
    Input("stat-carte", "value"),
    Input("dept-store", "data"),
    Input("mode-selection", "value"),
    Input("f-dept", "value"),
    Input("f-commune", "value"),
    Input("f-dpe", "value"),
    Input("f-energie", "value"),
    Input("f-surface", "value"),
    Input("f-options", "value"))
def maj_carte(stat, selection, mode, depts, communes, dpes, energies,
              surface, options):
    _, t, _ = lire_filtres(depts, communes, dpes, energies, surface, options)
    return fig_carte(t, stat or "ecart_type", selection, mode or "click")


# 5) Panneau détail
@app.callback(
    Output("panneau-contenu", "children"),
    Input("dept-store", "data"),
    Input("f-dept", "value"),
    Input("f-commune", "value"),
    Input("f-dpe", "value"),
    Input("f-energie", "value"),
    Input("f-surface", "value"),
    Input("f-options", "value"))
def maj_panneau(selection, depts, communes, dpes, energies, surface, options):
    _, t, _ = lire_filtres(depts, communes, dpes, energies, surface, options)

    if not selection:
        return html.Div(
            "Utilise le menu latéral pour choisir un mode de sélection, "
            "puis clique (ou dessine un rectangle) sur la carte.",
            style={"fontSize": "0.85rem", "color": "#66758A", "lineHeight": "1.5"})

    sous = t.loc[t.dept_code.isin(selection)] if not t.empty else pd.DataFrame()
    liste_noms = ", ".join(f"{c} · {NOMS_DEPT.get(c, '')}" for c in selection)

    enfants = [
        html.Div(f"{len(selection)} département(s) sélectionné(s)",
                 style={"fontWeight": "600", "color": "#153859",
                        "marginBottom": "4px", "fontSize": "0.95rem"}),
        html.Div(liste_noms,
                 style={"fontSize": "0.78rem", "color": "#66758A",
                        "marginBottom": "10px", "lineHeight": "1.4",
                        "wordBreak": "break-word"}),
    ]
    if len(sous):
        enfants += [
            html.Div(f"{len(sous)} adresse(s)",
                     style={"fontSize": "0.82rem", "color": "#66758A",
                            "marginBottom": "8px"}),
            carte_metric("Écart moyen",
                         fmt(sous.ecart_kwh.mean(), 0) + " kWh"),
            html.Div(style={"height": "6px"}),
            carte_metric("Écart type",
                         fmt(sous.ecart_kwh.std(), 0) + " kWh"),
            html.Div("Répartition par classe DPE",
                     style={"fontSize": "0.82rem", "color": "#66758A",
                            "marginTop": "10px", "marginBottom": "4px"}),
        ]
        rep = sous.etiquette_dpe.value_counts().reindex(CLASSES, fill_value=0)
        lignes = [html.Div(f"Classe {c} : {int(rep[c])} adresse(s)",
                           style={"fontSize": "0.82rem", "color": "#273A50"})
                  for c in CLASSES if rep[c] > 0]
        enfants.append(html.Div(lignes))
    else:
        enfants.append(html.Div("Aucune adresse dans ces départements.",
                                style={"fontSize": "0.85rem", "color": "#66758A"}))
    return enfants


# 6) KPI
@app.callback(
    Output("kpi-1", "children"),
    Output("kpi-2", "children"),
    Output("kpi-3", "children"),
    Output("kpi-4", "children"),
    Input("f-dept", "value"),
    Input("f-commune", "value"),
    Input("f-dpe", "value"),
    Input("f-energie", "value"),
    Input("f-surface", "value"),
    Input("f-options", "value"))
def maj_kpi(depts, communes, dpes, energies, surface, options):
    _, _, k = lire_filtres(depts, communes, dpes, energies, surface, options)
    return (
        carte_metric("Logements · DPE", fmt(k["logements"], 0)),
        carte_metric("DPE moyen · kWh/an", fmt(k["dpe"], 0)),
        carte_metric("Enedis · kWh/an", fmt(k["enedis"], 0)),
        carte_metric("Écart moyen · kWh/an", fmt(k["ecart"], 0)),
    )


# 7) Graphique classes
@app.callback(
    Output("graph-classes", "figure"),
    Input("f-dept", "value"),
    Input("f-commune", "value"),
    Input("f-dpe", "value"),
    Input("f-energie", "value"),
    Input("f-surface", "value"),
    Input("f-options", "value"))
def maj_graph_classes(depts, communes, dpes, energies, surface, options):
    _, t, _ = lire_filtres(depts, communes, dpes, energies, surface, options)
    return fig_comparison(t, "etiquette_dpe",
                          "DPE et Enedis par classe observée")


# 8) Graphique énergie
@app.callback(
    Output("graph-energie", "figure"),
    Input("f-dept", "value"),
    Input("f-commune", "value"),
    Input("f-dpe", "value"),
    Input("f-energie", "value"),
    Input("f-surface", "value"),
    Input("f-options", "value"))
def maj_graph_energie(depts, communes, dpes, energies, surface, options):
    _, t, _ = lire_filtres(depts, communes, dpes, energies, surface, options)
    return fig_comparison(t, "energie",
                          "Comparaison par énergie principale", horizontal=True)


# 9) Téléchargement
@app.callback(
    Output("download-data", "data"),
    Input("btn-download", "n_clicks"),
    State("f-dept", "value"),
    State("f-commune", "value"),
    State("f-dpe", "value"),
    State("f-energie", "value"),
    State("f-surface", "value"),
    State("f-options", "value"),
    prevent_initial_call=True)
def telecharger(n, depts, communes, dpes, energies, surface, options):
    if not n:
        raise PreventUpdate
    _, t, _ = lire_filtres(depts, communes, dpes, energies, surface, options)
    return dcc.send_data_frame(t.to_csv, "comparaisons_2023.csv", index=False)


# 10) Visibilité des blocs
@app.callback(
    Output("bloc-kpi", "style"),
    Output("bloc-carte", "style"),
    Output("bloc-export", "style"),
    Input("aff-blocs", "value"))
def maj_visibilite(blocs):
    blocs = blocs or []
    return (
        {"marginBottom": "14px",
         "display": "block" if "kpi" in blocs else "none"},
        {"display": "block" if "carte" in blocs else "none"},
        {"marginBottom": "14px",
         "display": "block" if "export" in blocs else "none"},
    )


# 11) Visibilité individuelle des graphiques
@app.callback(
    Output("wrap-classes", "style"),
    Output("wrap-energie", "style"),
    Input("aff-blocs", "value"))
def maj_vis_graphs(blocs):
    blocs = blocs or []
    base_cls = {"background": "white", "border": "1px solid #E4EAF1",
                "borderRadius": "12px", "padding": "8px",
                "marginBottom": "10px"}
    base_en = {"background": "white", "border": "1px solid #E4EAF1",
               "borderRadius": "12px", "padding": "8px"}
    return (
        {**base_cls, "display": "block" if "classes" in blocs else "none"},
        {**base_en, "display": "block" if "energie" in blocs else "none"},
    )


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=False, port=8050)