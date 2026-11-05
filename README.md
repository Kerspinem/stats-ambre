# Synthèse Ambre — Fourmizzz S5

Collecte horaire du tdc de l'alliance AMBRE via l'API officielle des exports publics
(`/api/exports/`, fichier des joueurs), analyse des floods et page de synthèse (`docs/index.html`,
publiée par GitHub Pages). Exécution automatique toutes les heures par GitHub Actions
(`.github/workflows/collecte.yml`).

- `collect.py` : collecte (rattrapage des heures sautées) puis génération de la page.
- `analyse.py`, `feuilles.py`, `page.py` : déduction des attaques, indicateurs, page HTML.
- `roles.csv` : rôles et chaînes des joueurs (à modifier ici si ça change).
- `historique_*.csv`, `state.json` : données (mises à jour par le workflow).
