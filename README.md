# Enedis / DPE : les consommations réelles sont-elles représentatives des classes DPE ?

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-%E2%89%A51.40-FF4B4B?logo=streamlit&logoColor=white)
![Altair](https://img.shields.io/badge/Altair-dataviz-1f77b4)
![Données](https://img.shields.io/badge/donn%C3%A9es-open%20data-brightgreen)

Ce dépôt contient un dashboard **Streamlit / Altair** qui compare la consommation électrique **estimée** par le Diagnostic de Performance Énergétique (DPE) à la consommation électrique **mesurée** par Enedis.

> [!IMPORTANT]
> **Résultat principal** : le DPE reproduit bien la consommation électrique mesurée en classes B et C, mais la surestime fortement de D à G. Les gains annoncés par le DPE entre classes sont bien supérieurs aux gains mesurés.

> [!NOTE]
> Il s'agit d'une comparaison entre logements différents, **pas d'un avant/après travaux** : elle ne prouve pas qu'une rénovation ne rapporte rien.

<!-- Ajouter des captures d'écran dans un dossier docs/ puis décommenter :
![Vue d'ensemble](docs/apercu_vue_ensemble.png)
![Écarts et relations](docs/apercu_ecarts_relations.png)
-->

## Sommaire

1. [Utilisation en local](#1-utilisation-en-local)
2. [Données et périmètre](#2-données-et-périmètre)
3. [Question métier et approche](#3-question-métier-et-approche)
4. [Principaux résultats](#4-principaux-résultats-échantillon-de-référence-2024)
5. [KPI et interprétation](#5-kpi-et-interprétation)
6. [Choix techniques de la visualisation](#6-choix-techniques-de-la-visualisation)

## 1. Utilisation en local

**Fichiers nécessaires** (dans le même dossier) :
- [`app.py`](app.py) : l'application Streamlit / Altair ;
- [`donnees_appariees.csv`](donnees_appariees.csv) : les DPE appariés aux consommations Enedis 2023 et 2024.

**Lancement**, dans un terminal, depuis ce dossier (par exemple après `git clone` du dépôt) :

```bash
pip install streamlit altair pandas
streamlit run app.py
```

L'application s'ouvre sur http://localhost:8501. Il faut Streamlit 1.40 ou plus (boutons de sélection des classes). Les hauteurs des graphiques se règlent avec la variable `H` en haut de `app.py` si l'affichage ne tient pas sur votre écran.

### Structure du dépôt

```text
.
├── app.py                     # dashboard Streamlit / Altair
├── donnees_appariees.csv      # DPE appariés à Enedis 2023-2024
├── filtre_dpe.py              # (optionnel) filtrage du fichier DPE brut de l'ADEME
├── docs/                      # (optionnel) captures d'écran
└── README.md
```

## 2. Données et périmètre

| Source | Contenu | Période utilisée |
|---|---|---|
| ADEME, *DPE logements existants* (data.gouv.fr) | Classe DPE, surface, énergies, consommations estimées par usage | DPE établis de juillet 2021 à décembre 2024 |
| Enedis, [*Consommation annuelle résidentielle par adresse*](https://www.data.gouv.fr/datasets/consommation-annuelle-residentielle-par-adresse) | Consommation moyenne par logement d'une adresse, en kWh/an | Mesures 2023 et 2024 |

**Pourquoi ce choix de période.** Les DPE antérieurs à juillet 2021 ne séparent pas les sources d'énergie (électricité, gaz, autres) : on ne peut pas y isoler la consommation électrique, la seule comparable aux données Enedis. Nous avons donc retenu les DPE postérieurs à la réforme de juillet 2021. Les consommations Enedis couvrent deux années (2023 et 2024), ce qui permet de vérifier la stabilité des résultats ; ce n'est pas une analyse d'évolution dans le temps.

**Construction du jeu de données.**
- Les DPE sont filtrés : électricité comme première ou seconde énergie, appartements et immeubles, adresse correctement géocodée (score BAN ≥ 0,7), puis dédoublonnés (DPE remplacés écartés).
- L'appariement se fait par code commune et adresse normalisée (texte, sans appel à l'API BAN).
- Enedis ne publie que les adresses de 10 logements ou plus : les maisons individuelles sont donc absentes de l'analyse.
- Sur 16 806 DPE, 6 226 sont retrouvés dans les adresses Enedis 2024 (37 %).
- Filtres du dashboard par défaut : surface de 15 à 300 m², consommation mesurée de 300 à 20 000 kWh/an, logements tout électriques, DPE cohérents (part électrique estimée ≤ 105 % de la consommation totale du DPE). Cet échantillon de référence compte environ 2 400 DPE en 2024.

## 3. Question métier et approche

**Question globale** : les consommations réelles d'énergie sont-elles représentatives des classes théoriques du DPE ?

Questions déclinées :
1. Le DPE reflète-t-il la consommation électrique mesurée, en moyenne et par classe ?
2. Quelle variabilité reste-t-il, due aux comportements et aux modes de vie ?
3. Quel gain, en kWh et en euros, obtient-on d'une classe à l'autre ?
4. Peut-on s'appuyer sur le DPE seul pour chiffrer les économies d'une rénovation ?

**Approche.** L'étude porte sur les écarts, les médianes et la variabilité des consommations par classe de DPE. Elle ne mesure pas l'effet de travaux : on compare des logements différents, pas un même logement avant et après rénovation.

## 4. Principaux résultats (échantillon de référence, 2024)

- Le mesuré représente **87 %** de l'estimé en médiane, et 64 % des logements consomment moins que l'estimation.
- Le DPE colle à la mesure en **classes B et C** (ratio de 112 % et 102 %), puis la **surestime fortement de D à G** : le mesuré vaut 76, 56, 48 puis 32 % de l'estimé.
- Les gains mesurés entre classes sont faibles et irréguliers, parfois négatifs, alors que le DPE annonce des milliers de kWh entre G et C (exemple à 0,25 €/kWh : passage de G à F, 508 €/an annoncés contre 41 € mesurés).
- La corrélation entre estimé et mesuré, logement par logement, est faible (0,15) : l'étiquette prédit mal la facture d'un logement donné.
- Le résultat est **stable entre 2023 et 2024** (ratio de 87,6 % puis 87,8 %). La consommation d'une même adresse varie d'environ 5 % d'une année sur l'autre, très en dessous des écarts observés en classes D à G.

Causes possibles de l'écart, **non démontrées par ces données** : restriction de chauffage dans les logements les moins performants, taux d'occupation, hypothèses conventionnelles du calcul 3CL.

## 5. KPI et interprétation

| KPI | Définition | Interprétation |
|---|---|---|
| Ratio mesuré / estimé | Médiane, par logement, de la consommation mesurée divisée par l'estimation électrique du DPE | Inférieur à 100 % : le DPE surestime la consommation réelle. Valeur de référence : 87 % |
| Part de logements sous l'estimation | Part des DPE dont le mesuré est inférieur à l'estimé | Proche de 50 % si le DPE est non biaisé. Référence : 64 % (5 % en A, 47 % en C, 98 % en G) |
| Écart médian et dispersion | Mesuré moins estimé, en kWh/an (médiane, écart-type) | La dispersion (écart-type de 3 101 kWh/an) est presque aussi grande que la consommation médiane : forte variabilité des modes de vie |
| Consommation par m² | Médiane en kWh/m²/an, mesurée et estimée | Permet de comparer des logements de tailles différentes |
| Gain par changement de classe | Médiane de la classe de départ moins celle de la classe d'arrivée (kWh/an, puis €/an au tarif choisi) | Compare le gain annoncé par le DPE au gain mesuré. Un gain négatif signifie que la classe d'arrivée consomme plus en réel |
| Taux d'appariement | DPE retrouvés dans Enedis / DPE fournis | Qualité du croisement (37 %) : les résultats valent pour l'intersection des deux fichiers, pas pour toute la France |
| Effectif par classe | Nombre de DPE par classe | Fiabilité : les classes A, F et G ont peu de logements (21, 81 et 47 en 2024) et sont à interpréter avec prudence |

**KPI par source.**
- *Enedis 2024* : 426 883 adresses résidentielles, 9,72 millions de logements, consommation moyenne par logement de 2 049 kWh/an en médiane (25 % à 75 % : 1 507 à 3 138).
- *DPE (extrait filtré)* : classes C et D majoritaires (31 % et 34 %), surface médiane de 51 m², 56 % de logements tout électriques.
- Ces deux jeux décrivent des populations différentes (Enedis : toutes les consommations de toutes les adresses de 10 logements ou plus ; DPE : logements diagnostiqués lors d'une vente ou d'une location) et ne se comparent qu'après appariement.

## 6. Choix techniques de la visualisation

| Outil | Justification |
|---|---|
| **Streamlit** | Dashboard en Python pur, sans développement web. Barre latérale de filtres, onglets et indicateurs prêts à l'emploi : adapté à un prototype exploratoire |
| **Altair** | Grammaire déclarative (un graphique = des données + des encodages), lisible et facile à modifier. Ses sélections permettent le *brushing & linking* : au sein d'une même composition, la sélection d'une classe ou d'une zone du nuage se propage aux autres graphiques côté navigateur |
| **pandas** | Filtrage, agrégation (médianes, ratios) et calcul des écarts |

**Principes de conception appliqués** (cours de data visualisation) :
- vue d'ensemble d'abord, filtres, puis détails à la demande (info-bulles) : mantra de Shneiderman ;
- écran unique, sans scroll, 4 KPI et 3 graphiques par onglet, filtres visibles dans la barre latérale avec rappel des filtres actifs et bouton de réinitialisation ;
- *data-ink ratio* : pas d'effets décoratifs, grilles discrètes, titres descriptifs, pas de camembert ;
- **accessibilité** : les couleurs officielles du DPE sont utilisées, mais les lettres A à G figurent toujours sur les axes et dans les légendes ; une option « palette adaptée au daltonisme » est proposée, et les séries mesuré / estimé sont en bleu et orange.

