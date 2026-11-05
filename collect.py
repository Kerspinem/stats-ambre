#!/usr/bin/env python3
"""Collecte horaire du terrain de chasse (tdc) de l'alliance AMBRE, serveur 5 de Fourmizzz,
via l'API officielle des exports publics (fichier des joueurs seulement). Une requête pour la liste des
versions, puis une par version manquante (rattrapage des heures sautées, 48 au plus), espacées de 2 s."""
import csv, json, os, sys, time, urllib.request
from collections import defaultdict
from datetime import datetime, timezone
import analyse

BASE = "https://s5.fourmizzz.fr/api/exports/"
TAG = "AMBRE"
DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(DIR, "state.json")
CSV_AL = os.path.join(DIR, "historique_alliance.csv")
CSV_PL = os.path.join(DIR, "historique_joueurs.csv")
CSV_ROLES = os.path.join(DIR, "roles.csv")
NUMBERS = os.path.join(DIR, "ambre.numbers")
MAX_RATTRAPAGE = 48
MAX_COMPLETER = int(os.environ.get("COMPLETER_MAX", "40"))  # versions complétées par exécution (totaux d'alliance)
EXTRA_IDS = {572}  # Oseil (alliance Fast) : seul joueur externe suivi

AL_COLS = ["version", "date_utc", "terrain_total", "variation_horaire", "ecart_heures", "source",
           "membres", "fourmiliere", "techno", "trophees",
           "rang_membres", "rang_tdc", "rang_tdc_membre", "rang_fourmiliere", "rang_techno", "rang_trophees", "nb_alliances"]
PL_COLS = ["version", "date_utc", "id", "pseudo", "alliance", "terrain", "variation_horaire", "ecart_heures", "source"]


def get(url):
    """Lit un JSON de l'API ; jusqu'à 4 essais (réseau instable sur les serveurs partagés)."""
    req = urllib.request.Request(url, headers={"User-Agent": "ambre-history-collector"})
    for essai in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if essai == 3:
                raise
            time.sleep(3 * 2 ** essai)


def parse(v):
    return datetime.strptime(v, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)


def append(path, cols, rows):
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(cols)
        w.writerows(rows)


def lire(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.reader(f))


def feuille_variations():
    """Une ligne par heure, une colonne par joueur (ordre des rangs), valeur = variation du tdc."""
    roles = lire(CSV_ROLES)[1:]
    pl = lire(CSV_PL)[1:]
    ordre = [r[1] for r in roles]
    ordre += sorted({r[3] for r in pl} - set(ordre), key=str.lower)
    var, dates = {}, {}
    for r in pl:
        var[(r[0], r[3])] = r[6]
        dates[r[0]] = r[1]
    tot = {r[0]: r[3] for r in lire(CSV_AL)[1:]}
    lignes = [["date_utc"] + ordre + ["TOTAL alliance"]]
    for v in sorted(dates):
        lignes.append([dates[v]] + [var.get((v, n), "") for n in ordre] + [tot.get(v, "")])
    return lignes


def contexte_periodes():
    """Périodes journalières (premier relevé UTC d'un jour -> premier du suivant ; la dernière va au relevé le plus
    récent) et chasse estimée des chasseurs : somme des gains horaires positifs, donc un minimum (une perte dans la
    même heure que la chasse la masque)."""
    pl = lire(CSV_PL)[1:]
    versions = sorted({r[0] for r in pl})
    dates = {r[0]: r[1] for r in pl}
    source = {r[0]: r[8] for r in pl}
    debuts = sorted({min(v for v in versions if v[:8] == j) for j in {v[:8] for v in versions}})
    periodes = list(zip(debuts, debuts[1:]))
    if versions[-1] != debuts[-1]:
        periodes.append((debuts[-1], versions[-1]))
    gains = defaultdict(list)  # pseudo -> [(version, gain horaire > 0)]
    for r in pl:
        if r[8] == "horaire" and r[6] != "" and int(r[6]) > 0:
            gains[r[3]].append((r[0], int(r[6])))

    def horaires(d, f):
        return [v for v in versions if d <= v <= f and source[v] == "horaire"]

    def chasse(n, d, f):
        return sum(g for v, g in gains[n] if d < v <= f)

    return pl, versions, dates, source, periodes, horaires, chasse


def fmt(x):
    return f"{x:,}".replace(",", " ")


def feuille_flux(lignes_att, chaine):
    """Flux de tdc d'une chaîne, du bas (chasseurs) vers le haut (greniers). Chaque ligne donne le montant du jour
    et sa part du total chassé par les chasseurs de la chaîne ce jour-là : pour les chasseurs, leur chasse ; pour
    les autres membres, le total des floods qu'ils ont envoyés. Rouge sous 50 % du chassé."""
    roles = [r for r in lire(CSV_ROLES)[1:] if r[8] == chaine and r[7] == "Actif"]
    pos = defaultdict(list)
    for r in roles:
        pos[int(r[9])].append(r[1])
    bas = max(pos)
    nom = lambda p: "Chasseurs" if p == bas else "/".join(pos[p])
    _, _, dates, _, periodes, horaires_de, chasse = contexte_periodes()
    chasseurs = pos[bas]
    membres = {n for p in pos.values() for n in p}
    h1, h2 = ["ligne (du bas vers le haut)"], [""]
    for d, f in periodes:
        h1 += [f"{dates[d][:10]}", ""]
        h2 += ["montant", "% du chassé"]
    lignes, styles = [h1, h2], {}
    # (libellé, fonction montant(d, f), colorier ?)
    specs = [("Chasse totale des chasseurs (entrée)", lambda d, f: sum(chasse(n, d, f) for n in chasseurs), False)]
    specs += [(f"   dont {n}", (lambda n: lambda d, f: chasse(n, d, f))(n), False) for n in chasseurs]
    for p in range(bas - 1, 0, -1):  # chaque membre : total des floods qu'il a envoyés (toutes cibles)
        for n in pos[p]:
            specs.append((f"{n} ({chaine} {p})",
                          (lambda n: lambda d, f: sum(a[4] for a in lignes_att if d < a[0] <= f and a[2] == n))(n), True))
    for i, (label, fonction, colorier) in enumerate(specs, start=2):
        ligne = [label]
        for k, (d, f) in enumerate(periodes):
            if len(horaires_de(d, f)) < 2:
                ligne += ["", ""]
                continue
            m = fonction(d, f)
            total = lignes[2][1 + 2 * k] if i > 2 else m
            pct = round(100 * m / total) if total else ""
            ligne += [m, pct]
            if colorier and pct != "" and pct < 50:
                styles[(i, 2 + 2 * k)] = "rouge"
        lignes.append(ligne)
    return lignes, styles


def build_numbers():
    lignes_att, _, _ = analyse.analyser(CSV_PL, CSV_ROLES)
    import feuilles as fe
    D = fe.calculer(lignes_att)
    import page
    page.ecrire(lignes_att, D, max(r[1] for r in D["pl"]) + " UTC")
    try:
        from numbers_parser import Document
    except ImportError:  # exécution dans le cloud : seule la page web est produite
        return
    doc = Document()
    attaques = [analyse.COLS] + lignes_att
    # (nom, lignes, colonnes numériques)
    feuilles = [
        ("Synthèse 1j", None, set()),
        ("Synthèse 3j", None, set()),
        ("Synthèse 7j", None, set()),
        ("Tableau journalier", None, set()),
        ("Flux ouest", None, set()),
        ("Flux est", None, set()),
        ("Attaques", attaques, {4}),
    ]
    from numbers_parser import RGB
    doc.add_style(name="rouge", bg_color=RGB(248, 203, 203), font_color=RGB(150, 20, 20))
    doc.add_style(name="jaune", bg_color=RGB(255, 242, 190), font_color=RGB(125, 95, 0))
    doc.add_style(name="orange", bg_color=RGB(255, 217, 170), font_color=RGB(140, 70, 0))
    doc.add_style(name="vert", bg_color=RGB(204, 236, 204), font_color=RGB(20, 100, 20))
    for i, (nom, lignes, nums) in enumerate(feuilles):
        styles = {}
        if lignes is None:
            if nom == "Tableau journalier":
                lignes, styles = fe.feuille_journaliere(lignes_att, D)
            elif nom.startswith("Synthèse"):
                lignes, styles = fe.feuille_synthese(lignes_att, D, int(nom.split()[-1].rstrip("j")))
            else:
                lignes, styles = feuille_flux(lignes_att, nom.split()[-1])
        largeur = max(len(l) for l in lignes)
        lignes = [l + [""] * (largeur - len(l)) for l in lignes]
        if i == 0:
            doc.sheets[0].name = nom
        else:
            doc.add_sheet(nom)
        table = doc.sheets[-1].tables[0]
        table.num_header_rows = 1
        table.num_header_cols = 0
        if len(lignes[0]) > table.num_cols:
            table.add_column(num_cols=len(lignes[0]) - table.num_cols)
        if len(lignes) > table.num_rows:
            table.add_row(num_rows=len(lignes) - table.num_rows)
        for r, ligne in enumerate(lignes):
            for c, val in enumerate(ligne):
                if r > 0 and val != "" and (nums is None and c > 0 or nums is not None and c in nums):
                    val = int(val)
                if val != "":
                    table.write(r, c, val, style=styles.get((r, c)))
    tmp = NUMBERS + ".tmp"
    doc.save(tmp)
    os.replace(tmp, NUMBERS)


def totaux(players):
    """Totaux de l'alliance (membres, fourmilière, technologie, trophées) puis son classement parmi toutes les
    alliances du serveur pour chacune des 6 données (membres, tdc, tdc par membre, fourmilière, techno, trophées)."""
    stats = {}
    for p in players:
        if not p["alliance"]:
            continue
        d = stats.setdefault(p["alliance"], [0, 0, 0, 0, 0])
        d[0] += 1
        d[1] += p["field"]
        d[2] += p["buildingScore"]
        d[3] += p["technologyScore"]
        d[4] += p["trophyScore"]
    moi = stats.get(TAG, [0] * 5)
    par_membre = lambda d: d[1] / d[0] if d[0] else 0

    def rang(f):
        return 1 + sum(1 for d in stats.values() if f(d) > f(moi))

    return [moi[0], moi[2], moi[3], moi[4], rang(lambda d: d[0]), rang(lambda d: d[1]), rang(par_membre),
            rang(lambda d: d[2]), rang(lambda d: d[3]), rang(lambda d: d[4]), len(stats)]


def completer_totaux():
    """Complète les anciens relevés d'alliance qui n'ont pas encore les totaux (les plus récents d'abord)."""
    if not os.path.exists(CSV_AL):
        return
    rows = lire(CSV_AL)
    data = [dict(zip(AL_COLS, r + [""] * (len(AL_COLS) - len(r)))) for r in rows[1:]]
    manquants = sorted((r for r in data if r["nb_alliances"] == ""), key=lambda r: r["version"], reverse=True)[:MAX_COMPLETER]
    for i, r in enumerate(manquants):
        if i:
            time.sleep(2)
        try:
            valeurs = totaux(get(f"{BASE}players/?version={r['version']}"))
            for cle, v in zip(AL_COLS[6:], valeurs):
                r[cle] = v
        except Exception as e:  # version introuvable : on la laisse vide
            print("totaux indisponibles", r["version"], e)
    if manquants:
        with open(CSV_AL, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=AL_COLS)
            w.writeheader()
            w.writerows(data)
        print("totaux complétés :", len(manquants))


def traiter(state, version, players):
    """Enregistre un relevé : total de l'alliance, tdc des joueurs suivis, variations."""
    t = parse(version)
    d = t.strftime("%Y-%m-%d %H:%M")
    gap = round((t - parse(state["last"])).total_seconds() / 3600) if state["last"] else ""
    total = sum(p["field"] for p in players if p["alliance"] == TAG)
    prev = state.get("total")
    append(CSV_AL, AL_COLS, [[version, d, total, total - prev if prev is not None else "", gap, "horaire"] + totaux(players)])
    state["total"] = total
    # on continue de suivre un joueur après son départ de l'alliance
    ids = set(state["ids"]) | EXTRA_IDS | {p["id"] for p in players if p["alliance"] == TAG}
    rows = []
    for p in sorted(players, key=lambda p: p["id"]):
        if p["id"] not in ids:
            continue
        prev = state["terrain"].get(str(p["id"]))
        rows.append([version, d, p["id"], p["pseudo"], p["alliance"] or "", p["field"],
                     p["field"] - prev if prev is not None else "", gap, "horaire"])
        state["terrain"][str(p["id"])] = p["field"]
    append(CSV_PL, PL_COLS, rows)
    state["ids"] = sorted(ids)
    state["pos"] = {p["pseudo"]: [p["x"], p["y"]] for p in players if p["id"] in ids}
    state["last"] = version
    return len(rows)


def collecter():
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    state.setdefault("last", None)
    state.setdefault("ids", [])
    state.setdefault("terrain", {})
    liste = sorted(get(BASE).get("players", []))
    nouvelles = [v for v in liste if state["last"] is None or v > state["last"]]
    if state["last"] is None:
        nouvelles = nouvelles[-1:]
    nouvelles = nouvelles[-MAX_RATTRAPAGE:]
    if not nouvelles:
        print("rien de nouveau", liste[-1] if liste else None)
    for i, v in enumerate(nouvelles):
        if i:
            time.sleep(2)
        n = traiter(state, v, get(f"{BASE}players/?version={v}"))
        json.dump(state, open(STATE, "w"))
        print("ok", v, n, "joueurs")
    if "pos" not in state and liste:  # positions absentes de l'état (anciennes versions du script)
        time.sleep(2)
        ids = set(state["ids"]) | EXTRA_IDS
        state["pos"] = {p["pseudo"]: [p["x"], p["y"]] for p in get(f"{BASE}players/?version={liste[-1]}") if p["id"] in ids}
        json.dump(state, open(STATE, "w"))
    completer_totaux()


def main():
    # une panne réseau ne doit pas empêcher de republier la page avec les données déjà enregistrées
    try:
        collecter()
    except Exception as e:
        print(f"::warning::collecte impossible ce coup-ci : {e}")
    build_numbers()  # toujours : la page affiche l'heure de génération


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("erreur:", e, file=sys.stderr)
        sys.exit(1)
