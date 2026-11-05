"""Déduction des attaques de tdc (« floods ») et indicateurs d'activité.

Hypothèses : le tdc ne change que par attaque et par chasse (chasseurs seulement).
Une attaque déplace X de la cible vers l'attaquant, avec tdc_cible entre
tdc_attaquant/2 et 3*tdc_attaquant. Dans la chaîne, le rang n attaque le rang n+1.
Limites : un instantané par heure (chaînes A->B->C et allers-retours dans la même
heure s'annulent) ; plusieurs attaques d'une heure sont fusionnées. Les relevés de
rattrapage (un par jour) ne servent jamais à attribuer des attaques."""
import csv
from collections import deque, defaultdict
from datetime import datetime, timedelta
from statistics import median

PRIORITE = {"Chasseur": 0, "Passeur": 1, "Grenier": 2}
COLS = ["version", "date_utc", "attaquant", "cible", "montant", "confiance", "cibles_possibles", "remarque"]
ACT_COLS = ["pseudo", "role", "chaine", "position", "tdc", "variation_tdc_24h", "variation_tdc_7j",
            "floods_lances_24h", "floods_lances_7j", "floods_subis_24h", "floods_subis_7j",
            "heures_actives_7j", "dernier_flood_lance", "gain_chasse_median_par_h", "rang_dans_role"]
EXT = "(externe inconnu)"


def _dt(v):
    return datetime.strptime(v, "%Y%m%d%H%M")


def lire_roles(path):
    with open(path, encoding="utf-8") as f:
        return {r["pseudo"]: r for r in csv.DictReader(f)}


def lire_historique(path):
    h = defaultdict(dict)  # version -> id -> (pseudo, terrain)
    dates, source = {}, {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            h[r["version"]][int(r["id"])] = (r["pseudo"], int(r["terrain"]))
            dates[r["version"]] = r["date_utc"]
            source[r["version"]] = r.get("source") or "horaire"
    return h, dates, source


def _maxflow(gains, pertes, aretes, pref):
    """Edmonds-Karp : source -> attaquants -> cibles -> puits. pref : ordre des arêtes (petit = préféré)."""
    cap = defaultdict(int)
    adj = defaultdict(list)

    def add(u, v, c):
        if v not in adj[u]:
            adj[u].append(v)
        if u not in adj[v]:
            adj[v].append(u)
        cap[(u, v)] += c

    for a, g in gains.items():
        add("S", ("A", a), g)
    for b, p in pertes.items():
        add(("B", b), "T", p)
    for e in sorted(aretes, key=lambda e: pref(e)):
        add(("A", e[0]), ("B", e[1]), 10 ** 12)
    flux = defaultdict(int)
    while True:
        prec = {"S": None}
        q = deque(["S"])
        while q and "T" not in prec:
            u = q.popleft()
            for v in adj[u]:
                if v not in prec and cap[(u, v)] > 0:
                    prec[v] = u
                    q.append(v)
        if "T" not in prec:
            break
        chemin, v = [], "T"
        while prec[v] is not None:
            chemin.append((prec[v], v))
            v = prec[v]
        m = min(cap[e] for e in chemin)
        for (u, v) in chemin:
            cap[(u, v)] -= m
            cap[(v, u)] += m
            if u != "S" and v != "T" and u[0] == "A":
                flux[(u[1], v[1])] += m
            elif u != "S" and v != "T" and u[0] == "B":
                flux[(v[1], u[1])] -= m
    return {e: f for e, f in flux.items() if f > 0}


def analyser(csv_pl, csv_roles):
    """Renvoie (lignes d'attaques, cadences de chasse par id, noms par id)."""
    roles = lire_roles(csv_roles)
    h, dates, source = lire_historique(csv_pl)
    versions = sorted(h)
    noms = {i: n for v in versions for i, (n, _) in h[v].items()}
    info = lambda i: roles.get(noms[i], {})
    type_de = lambda i: info(i).get("type", "")  # externes suivis : ""
    pos_de = lambda i: (info(i).get("chaine", ""), int(info(i)["position"]) if info(i).get("position") else None)
    exclu = lambda i: info(i).get("etat", "Actif") != "Actif"
    chasse = defaultdict(list)  # id -> gains horaires observés des chasseurs (relevés horaires seulement)
    sortie = []
    for v0, v1 in zip(versions, versions[1:]):
        heures = max(1, round((_dt(v1) - _dt(v0)).total_seconds() / 3600))
        rattrapage = "rattrapage" in (source[v0], source[v1])
        gains, pertes, avant, notes = {}, {}, {}, {}
        for i in h[v1]:
            if i not in h[v0] or exclu(i):
                continue
            avant[i] = h[v0][i][1]
            d = h[v1][i][1] - avant[i]
            if rattrapage:
                continue
            if type_de(i) == "Chasseur":
                # la chasse arrive par à-coups (pas de cadence horaire régulière) : un gain de chasseur
                # est attribué à la chasse ; une baisse est une perte (minimale si la chasse l'a compensée)
                if d > 0:
                    chasse[i].append(d / heures)
                    continue
                if d < 0:
                    notes[i] = "perte minimale (chasse possible)"
            if d > 0:
                gains[i] = d
            elif d < 0:
                pertes[i] = -d
        if rattrapage:
            continue
        faisable = lambda a, b: a != b and avant[a] / 2 <= avant[b] <= 3 * avant[a]
        chaine = set()
        for a in gains:
            for b in pertes:
                ca, pa = pos_de(a)
                cb, pb = pos_de(b)
                if faisable(a, b) and ca and ca == cb and pb == pa + 1:
                    chaine.add((a, b))
        flux1 = _maxflow(gains, pertes, chaine, lambda e: e)
        recu, donne = defaultdict(int), defaultdict(int)
        for (a, b), x in flux1.items():
            recu[a] += x
            donne[b] += x
        gains2 = {a: g - recu[a] for a, g in gains.items() if g - recu[a] > 0}
        pertes2 = {b: p - donne[b] for b, p in pertes.items() if p - donne[b] > 0}
        hors = {(a, b) for a in gains2 for b in pertes2 if faisable(a, b)}
        flux2 = _maxflow(gains2, pertes2, hors,
                         lambda e: PRIORITE.get(type_de(e[1]), 1) - PRIORITE.get(type_de(e[0]), 1))
        for (a, b), x in flux2.items():
            recu[a] += x
            donne[b] += x
        date = dates[v1]

        def remarque(a, b, x):
            rem = []
            if x > 0.2 * avant[b]:
                rem.append("> 20 % du tdc de la cible : plusieurs attaques")
            rem += [n for n in (notes.get(a), notes.get(b)) if n]
            if heures > 1:
                rem.append(f"fenêtre de {heures} h")
            return "; ".join(rem)

        for (a, b), x in sorted(flux1.items()):
            att_b = [z for (z, y) in chaine if y == b]
            cib_a = [y for (z, y) in chaine if z == a]
            sur = (len(att_b) == 1 and x == pertes[b]) or (len(cib_a) == 1 and x == gains[a])
            sortie.append([v1, date, noms[a], noms[b], x, "certain" if sur else "plausible",
                           "" if sur else ", ".join(sorted(noms[y] for y in cib_a)), remarque(a, b, x)])
        for (a, b), x in sorted(flux2.items()):
            if a in roles_ids(noms, roles) and b in roles_ids(noms, roles):
                conf, cand = "hors chaîne", ""
            else:
                cib = [y for (z, y) in hors if z == a]
                att = [z for (z, y) in hors if y == b]
                sur = len(cib) == 1 or len(att) == 1
                conf, cand = ("certain", "") if sur else ("plausible", ", ".join(sorted(noms[y] for y in cib)))
            sortie.append([v1, date, noms[a], noms[b], x, conf, cand, remarque(a, b, x)])
        for a, g in gains.items():
            if g - recu[a] > 0:
                sortie.append([v1, date, noms[a], EXT, g - recu[a], "externe", "", notes.get(a, "")])
        for b, p in pertes.items():
            if p - donne[b] > 0:
                sortie.append([v1, date, EXT, noms[b], p - donne[b], "externe", "", notes.get(b, "")])
    cadences = {i: median(c) for i, c in chasse.items() if len(c) >= 3}
    return sortie, cadences, noms


def roles_ids(noms, roles):
    return {i for i, n in noms.items() if n in roles}


def activite(csv_pl, csv_roles, attaques, cadences):
    """Une ligne par membre actif : volumes de floods (24 h / 7 j) et rang parmi les joueurs de même rôle."""
    roles = lire_roles(csv_roles)
    h, dates, source = lire_historique(csv_pl)
    if not h:
        return []
    versions = sorted(h)
    fin = _dt(versions[-1])
    noms = {i: n for v in versions for i, (n, _) in h[v].items()}
    par_nom = {n: i for i, n in noms.items()}

    def tdc_a(i, dt):  # dernier tdc connu au plus tard à dt
        vs = [v for v in versions if _dt(v) <= dt and i in h[v]]
        return h[vs[-1]][i][1] if vs else None

    stat = {}
    for n, r in roles.items():
        if r.get("etat", "Actif") != "Actif" or n not in par_nom:
            continue
        i = par_nom[n]
        now = tdc_a(i, fin)
        v24, v7 = tdc_a(i, fin - timedelta(hours=24)), tdc_a(i, fin - timedelta(days=7))
        s = {"lance": [0, 0], "subi": [0, 0], "heures": set(), "dernier": ""}
        for a in attaques:
            t = _dt(a[0])
            if t <= fin - timedelta(days=7):
                continue
            recent = t > fin - timedelta(hours=24)
            if a[2] == n:
                s["lance"][1] += a[4]
                s["lance"][0] += a[4] if recent else 0
                s["heures"].add(a[0])
                s["dernier"] = a[1]
            if a[3] == n:
                s["subi"][1] += a[4]
                s["subi"][0] += a[4] if recent else 0
                s["heures"].add(a[0])
        stat[n] = (r, i, now, now - v24 if v24 is not None else "", now - v7 if v7 is not None else "", s)
    par_role = defaultdict(list)
    for n, (r, i, *_rest) in stat.items():
        # chasseurs : classés sur la cadence de chasse ; autres : sur le volume lancé en 7 j
        cle = cadences.get(i, 0) if r["type"] == "Chasseur" else stat[n][5]["lance"][1]
        par_role[r["type"]].append((cle, n))
    rang = {}
    for role, lst in par_role.items():
        for k, (_, n) in enumerate(sorted(lst, reverse=True), 1):
            rang[n] = f"{k}/{len(lst)}"
    lignes = []
    for n, (r, i, now, d24, d7, s) in sorted(stat.items(), key=lambda kv: int(kv[1][0]["rang"])):
        lignes.append([n, r["type"], r["chaine"], r["position"], now, d24, d7, s["lance"][0], s["lance"][1],
                       s["subi"][0], s["subi"][1], len(s["heures"]), s["dernier"],
                       round(cadences[i]) if i in cadences else "", rang[n]])
    return lignes
