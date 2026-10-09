# Habitat 2023 — DPE et Enedis par Ala Eddine Yakoubi et Victor Eloy

Application locale d'apprentissage, préparée à partir de `app.py`, `dataset_final_2023.csv` et `departements.geojson`. Le dataset final est déjà fourni : aucune préparation n'est nécessaire pour démarrer.

## Démarrage

Extraire l'archive. Ouvrir un terminal dans le dossier qui contient `app.py` :

python \-m pip install \-r requirements.txt

python app.py

Ouvrir [http\://localhost:8050](http://localhost:8050). Arrêter avec `Ctrl+C`. Python 3.11 ou 3.12 est recommandé.

Pour isoler les dépendances sous Windows, sans activer PowerShell :

py \-m venv .venv

.\\.venv\\Scripts\\python.exe \-m pip install \-r requirements.txt

.\\.venv\\Scripts\\python.exe app.py

## Outils utilisés et justification

| Outil | Justification |
| :---- | :---- |
| **Plotly** | Graphiques interactifs sans configuration (survol, zoom, sélection rectangulaire ou au lasso, légende cliquable). Il couvre les types de graphiques nécessaires ici : nuage de points, boîtes à moustaches, histogrammes, barres groupées. |
| **Dash** | Permet de relier les graphiques entre eux (*brushing & linking*) et aux filtres par des fonctions de rappel en Python : une sélection dans un graphique met à jour les autres et les KPI. Offre aussi un contrôle précis de la mise en page (écran unique, barre latérale, onglets). |
| **Pandas** | Filtrage, agrégation (médianes, ratios) et calcul des écarts. |

## Ce qui a été préparé

| Étape | Résultat sur les fichiers fournis |
| :---- | :---- |
| DPE du fichier initial | 10 000 |
| DPE établis en 2023 | 847 |
| DPE de logements retenus | 846 (1 DPE immeuble exclu) |
| Lignes Enedis de 2023 | 156 667 |
| Adresses Enedis ambiguës écartées | 171, soit 344 lignes |
| DPE appariés à Enedis | 76, sur 41 adresses |
| DPE avec consommation simulée | 770 |
| Adresses ou unités techniques de comparaison | 689 |
| DPE avec coordonnées disponibles | 834 |

> 2023 désigne l'année d'établissement du DPE et l'année de consommation Enedis. Les 846 DPE ont toutefois été modifiés en 2026 dans cet export : les valeurs historiques exactes du diagnostic en 2023 ne sont pas récupérables ici.

## KPI

| Thème | KPI | Définition | Valeur de référence (2024) | Interprétation |
| :---- | :---- | :---- | :---- | :---- |
| **Fidélité du DPE** | Ratio mesuré / estimé | Médiane, par logement, de la consommation mesurée divisée par l'estimation électrique du DPE | 87 % | Inférieur à 100 % : le DPE surestime la consommation réelle |
|  | Part de logements sous l'estimation | Part des DPE dont le mesuré est inférieur à l'estimé | 64 % (5 % en A, 47 % en C, 98 % en G) | Proche de 50 % si le DPE est non biaisé |
|  | Consommation par m² | Médiane en kWh/m²/an, mesurée et estimée | 82 mesurés contre 97 estimés | Permet de comparer des logements de tailles différentes |
| **Variabilité** | Écart médian et dispersion | Mesuré moins estimé, en kWh/an (médiane, écart-type) | Médiane de −462 kWh/an, écart-type de 3 101 kWh/an | La dispersion est presque aussi grande que la consommation médiane : forte variabilité des modes de vie |
| **Bénéfices d'une rénovation** | Gain par changement de classe | Médiane de la classe de départ moins celle de la classe d'arrivée (kWh/an, puis €/an au tarif choisi) | De −272 à \+165 kWh/an mesurés, contre 157 à 2 034 annoncés (de −68 à \+41 €/an contre 39 à 509 €/an à 0,25 €/kWh) | Compare le gain annoncé par le DPE au gain mesuré ; un gain négatif signifie que la classe d'arrivée consomme plus en réel |
| **Qualité des données** | Taux d'appariement | DPE retrouvés dans Enedis / DPE fournis | 37 % | Les résultats valent pour l'intersection des deux fichiers, pas pour toute la France |
|  | Effectif par classe | Nombre de DPE par classe | A : 21, F : 81, G : 47 | Classes à interpréter avec prudence |

*Les valeurs de référence proviennent de l'analyse 2024 (2 425 DPE tout électriques, données cohérentes) ; elles ne correspondent pas au jeu 2023 décrit ci-dessus.*

## Fichiers

- `dataset_final_2023.csv` : dataset déjà calculé, UTF-8, séparateur virgule.  
- `app.py` : interface dash / plotly, filtres, huit graphiques, KPI et exports.  
- `requirements.txt` : quatre dépendances, versions utilisées pour les tests.  
- `departements.geojson` : fichier JSON avec les infos de départements / adresses.

## Références de méthode

- Enedis : consommation annuelle résidentielle par adresse  
- ADEME : DPE logements existants  
- IGN : algorithmes géodésiques

Les références décrivent les concepts ; aucune nouvelle donnée n'est téléchargée par le projet. Les données utilisées sont exclusivement les deux fichiers fournis et les compléments identifiés ci-dessus.