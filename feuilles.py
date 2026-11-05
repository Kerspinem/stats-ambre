"""Feuilles d'évaluation : tableau journalier (synthèse + détail par jour) et rapport « Semaine »."""
from collections import defaultdict

import collect

POSTES = ("Grenier", "Passeur", "Chasseur")
SEUIL_NOEUD = 50         # % du total chassé sous lequel un membre est considéré comme retenant le flux
SEUIL_INCERTAIN = 40     # % d'envois à cible incertaine (plusieurs candidats) au-dessus duquel les données sont fragiles
SEUIL_HORS = 30          # % d'envois hors chaîne au-dessus duquel on le signale
HORS_CHASSE = 5          # un flood hors alliance n'est compté « hors chaîne » que s'il dépasse ce % du tdc chassé du jour (chaîne du joueur)
JOUR_COMPLET = 20        # heures minimales pour qu'une période compte dans la synthèse


def fmt(x):
    return f"{x:,}".replace(",", " ")


def calculer(lignes_att):
    """Montant du jour (flood envoyé, ou chasse pour les chasseurs), part du chassé, part certaine, moyenne par
    poste et par chaîne, position par rapport à cette moyenne."""
    roles = {r[1]: dict(pseudo=r[1], type=r[4], chaine=r[8], pos=int(r[9]) if r[9] else 0, actif=r[7] == "Actif")
             for r in collect.lire(collect.CSV_ROLES)[1:]}
    pl, versions, dates, source, periodes, horaires_de, chasse = collect.contexte_periodes()
    alliance = {r[3]: r[4] for r in pl}
    from datetime import datetime
    info = []
    for d, f in periodes:
        h = round((datetime.strptime(f, "%Y%m%d%H%M") - datetime.strptime(d, "%Y%m%d%H%M")).total_seconds() / 3600)
        info.append(dict(d=d, f=f, jour=dates[d][:10], heures=h, valide=len(horaires_de(d, f)) >= 2))
    membres = [r for r in roles.values() if r["actif"]]
    gains_h = defaultdict(list)  # pseudo -> [(version, gain horaire > 0)] pour la régularité des chasseurs
    for r in pl:
        if r[8] == "horaire" and r[6] != "" and int(r[6]) > 0:
            gains_h[r[3]].append((r[0], int(r[6])))
    val = {}
    for k, p in enumerate(info):
        if not p["valide"]:
            continue
        chasse_chaine = {ch: sum(chasse(m["pseudo"], p["d"], p["f"]) for m in membres
                                 if m["type"] == "Chasseur" and m["chaine"] == ch) for ch in ("ouest", "est")}
        for m in membres:
            n = m["pseudo"]
            lances, subis, doute, indet = defaultdict(int), defaultdict(int), set(), 0
            cat = defaultdict(int)  # envoyé : incertain (plusieurs candidats) / hors chaîne (hors rang du dessous, extérieur inclus)
            actifs = set()
            for a in lignes_att:
                if p["d"] < a[0] <= p["f"]:
                    if a[2] == n:
                        lances[a[3]] += a[4]
                        # hors chaîne : flood vers un joueur hors alliance, au-delà de HORS_CHASSE % du chassé du jour
                        if a[3] not in roles and a[4] > HORS_CHASSE / 100 * chasse_chaine.get(m["chaine"], 0):
                            cat["hors"] += a[4]
                        if a[5] == "plausible":
                            cat["plausible"] += a[4]
                        actifs.add(a[0])
                        if a[5] != "certain":
                            indet += a[4]
                    if a[3] == n:
                        subis[a[2]] += a[4]
                    if a[5] in ("plausible", "hors chaîne") and n in (a[2], a[3]):
                        doute.add(a[3] if a[2] == n else a[2])
            chasseur = m["type"] == "Chasseur"
            envoye = sum(lances.values())
            montant = chasse(n, p["d"], p["f"]) if chasseur else envoye
            morceaux = [f"→ {c} {fmt(v)}{' ?' if c in doute else ''}" for c, v in sorted(lances.items(), key=lambda kv: -kv[1])]
            morceaux += [f"← {c} {fmt(v)}{' ?' if c in doute else ''}" for c, v in sorted(subis.items(), key=lambda kv: -kv[1])]
            if chasseur:  # régularité des chasseurs : heures où la chasse a progressé
                actifs = {v for v, g in gains_h[n] if p["d"] < v <= p["f"]}
            val[(n, k)] = dict(montant=montant, floods=" ; ".join(morceaux),
                               certain="" if chasseur or not envoye else round(100 * (envoye - indet) / envoye),
                               incertain="" if chasseur or not envoye else round(100 * cat["plausible"] / envoye),
                               hors="" if chasseur or not envoye else round(100 * cat["hors"] / envoye),
                               heures=len(actifs), actifs=sorted(actifs))
    # total chassé par chaîne et par période
    chasse_tot = {}
    for k, p in enumerate(info):
        if p["valide"]:
            for ch in ("ouest", "est"):
                chasse_tot[(ch, k)] = sum(val[(m["pseudo"], k)]["montant"] for m in membres
                                          if m["type"] == "Chasseur" and m["chaine"] == ch)
    # moyenne par poste et par chaîne, comparaison de chacun
    moy, pos = {}, {}
    for k, p in enumerate(info):
        if not p["valide"]:
            continue
        for ch in ("ouest", "est"):
            for t in POSTES:
                g = [m["pseudo"] for m in membres if m["type"] == t and m["chaine"] == ch]
                v = [val[(n, k)]["montant"] for n in g]
                if v:
                    mm = sum(v) / len(v)
                    moy[(t, ch, k)] = mm
                    for n in g:
                        x = val[(n, k)]["montant"]
                        pos[(n, k)] = -1 if x < mm else 1 if x > mm else 0
                        tot = chasse_tot[(ch, k)]
                        val[(n, k)]["pct_chasse"] = round(100 * x / tot) if tot else ""
    # flux avec l'extérieur (attributions), croissance totale, heures manquantes
    tous = set(roles)
    ext = {}
    for k, p in enumerate(info):
        if not p["valide"]:
            continue
        for ch in ("ouest", "est"):
            noms = {m["pseudo"] for m in membres if m["chaine"] == ch}
            gagne = sum(a[4] for a in lignes_att if p["d"] < a[0] <= p["f"] and a[2] in noms and a[3] not in tous)
            perdu = sum(a[4] for a in lignes_att if p["d"] < a[0] <= p["f"] and a[3] in noms and a[2] not in tous)
            ext[(ch, k)] = (gagne, perdu)
    al = collect.lire(collect.CSV_AL)[1:]
    al_tot = {r[0]: int(r[2]) for r in al}
    manquantes = {}
    for k, p in enumerate(info):
        manquantes[k] = sum(int(r[4]) - 1 for r in al if p["d"] < r[0] <= p["f"] and r[4] not in ("", "0", "1"))
    oseil = {k: (sum(a[4] for a in lignes_att if p["d"] < a[0] <= p["f"] and a[2] in tous and a[3] == "Oseil"),
                 sum(a[4] for a in lignes_att if p["d"] < a[0] <= p["f"] and a[3] in tous and a[2] == "Oseil"))
             for k, p in enumerate(info) if p["valide"]}
    return dict(roles=roles, membres=membres, info=info, val=val, moy=moy, pos=pos, chasse_tot=chasse_tot,
                alliance=alliance, pl=pl, ext=ext, al_tot=al_tot, manquantes=manquantes, oseil=oseil)


def pause_max(actifs, d, f):
    """Plus longue période sans activité, en heures, entre le début et la fin de la plage."""
    from datetime import datetime
    t = lambda v: datetime.strptime(v, "%Y%m%d%H%M")
    pts = [t(d)] + [t(v) for v in sorted(actifs)] + [t(f)]
    return round(max((b - a).total_seconds() for a, b in zip(pts, pts[1:])) / 3600)


def synthese(D, n):
    """Sur les jours complets : moyenne par jour, % incertain et % hors chaîne moyens, plus longue pause."""
    ks = [k for k, p in enumerate(D["info"]) if p["valide"] and p["heures"] >= JOUR_COMPLET]
    if not ks:
        return dict(moy="", inc="", hors="", pause="")
    V = [D["val"][(n, k)] for k in ks]
    inc = [v["incertain"] for v in V if v["incertain"] != ""]
    hors = [v["hors"] for v in V if v["hors"] != ""]
    actifs = [x for v in V for x in v["actifs"]]
    return dict(moy=round(sum(v["montant"] for v in V) / len(V)),
                inc=round(sum(inc) / len(inc)) if inc else "", hors=round(sum(hors) / len(hors)) if hors else "",
                pause=pause_max(actifs, D["info"][ks[0]]["d"], D["info"][ks[-1]]["f"]))


def feuille_journaliere(lignes_att, D=None):
    D = D or calculer(lignes_att)
    info, val = D["info"], D["val"]
    fixes = ["moy. / jour", "% incertain moy.", "% hors chaîne moy.", "pause max (h)"]
    nf = 2 + len(fixes)
    h1 = ["joueur", "rôle · chaîne", "synthèse (jours complets)"] + [""] * (len(fixes) - 1)
    h2 = ["", ""] + fixes
    for p in info:
        h1 += [f"{p['jour']} ({p['heures']} h)", "", "", "", ""]
        h2 += ["envoyé · chasse", "% du chassé", "% incertain", "% hors chaîne", "floods"]
    lignes, styles = [h1, h2], {}

    def ligne_joueur(m):
        n = m["pseudo"]
        S = synthese(D, n)
        ligne = [n, f"{m['type']} · {m['chaine']} {m['pos']}", S["moy"], S["inc"], S["hors"], S["pause"]]
        for k, p in enumerate(info):
            v = val.get((n, k))
            if not v:
                ligne += ["", "", "", "", "n/d"]
                continue
            ligne += [v["montant"], v.get("pct_chasse", ""), v["incertain"], v["hors"], v["floods"]]
        r = len(lignes)  # couleurs sur les colonnes de synthèse uniquement
        if S["inc"] != "" and S["inc"] > SEUIL_INCERTAIN:
            styles[(r, 3)] = "jaune"
        if S["hors"] != "" and S["hors"] > SEUIL_HORS:
            styles[(r, 4)] = "orange"
        return ligne

    for ch in ("ouest", "est"):
        lignes.append([f"CHAÎNE {ch.upper()}"])
        for t in POSTES:
            for m in sorted((m for m in D["membres"] if m["type"] == t and m["chaine"] == ch), key=lambda m: m["pos"]):
                lignes.append(ligne_joueur(m))
    externes = sorted({r[3] for r in D["pl"]} - set(D["roles"]), key=str.lower)
    if externes:
        lignes.append(["HORS ALLIANCE (suivi)"])
        for n in externes:
            ligne = [n, f"Externe ({D['alliance'].get(n, '')})"] + [""] * len(fixes)
            for k, p in enumerate(info):
                if not p["valide"]:
                    ligne += ["", "", "", "", "n/d"]
                    continue
                lances = defaultdict(int)
                subis = defaultdict(int)
                for a in lignes_att:
                    if p["d"] < a[0] <= p["f"]:
                        if a[2] == n:
                            lances[a[3]] += a[4]
                        if a[3] == n:
                            subis[a[2]] += a[4]
                morceaux = [f"→ {c} {fmt(v)}" for c, v in sorted(lances.items(), key=lambda kv: -kv[1])]
                morceaux += [f"← {c} {fmt(v)}" for c, v in sorted(subis.items(), key=lambda kv: -kv[1])]
                ligne += [sum(lances.values()), "", "", "", " ; ".join(morceaux)]
            lignes.append(ligne)
    return lignes, styles


PLAGES = (1, 3, 7)        # nombres de jours proposés (une feuille « Synthèse Nj » chacune)
SEUIL_TENDANCE = 0.15     # variation de la moyenne qui déclenche une flèche
SEUIL_HABITUDE = 70       # % de sa chasse habituelle sous lequel un chasseur est signalé


def _moyenne(v):
    return sum(v) / len(v) if v else None


def feuille_synthese(lignes_att, D, N):
    """Vue d'ensemble sur les N derniers jours complets : bilan par chaîne, origine du tdc, signaux, tous les joueurs."""
    info, val, roles = D["info"], D["val"], D["roles"]
    complets = [k for k, p in enumerate(info) if p["valide"] and p["heures"] >= JOUR_COMPLET]
    if not complets:
        return [["Pas encore de jour complet"]], {}
    ks = complets[-N:]
    avant = [k for k in complets if k < ks[0]]
    precedents = avant[-N:] if len(avant) >= -(-N // 2) else []
    habitude_ks = avant
    jours = [info[k]["jour"] for k in ks]
    manque = sum(D["manquantes"][k] for k in ks)
    L, styles = [], {}

    def pct(x, tot):
        return round(100 * x / tot) if tot else ""

    L.append([f"SYNTHÈSE — {len(ks)} jour{'s' if len(ks) > 1 else ''} complet{'s' if len(ks) > 1 else ''} : {jours[0]}"
              + (f" au {jours[-1]}" if len(ks) > 1 else "")
              + (f" (demandé : {N})" if len(ks) < N else "")])
    L.append([("Données : complètes sur la plage." if not manque else
               f"Données : {manque} h manquantes dans la plage (versions non publiées par l'API), les montants de ces heures sont regroupés.")
              + " Jours = jours UTC complets ; le jour en cours figure dans le Tableau journalier."])
    L.append([])

    # --- bilan des chaînes
    L.append(["1. BILAN DES CHAÎNES"])
    L.append(["chaîne", "chassé", "reçu par le grenier de tête", "% du chassé", "goulot principal", "gagné sur l'extérieur",
              "perdu vers l'extérieur", "net extérieur"])
    r_chaine = {}
    for ch in ("ouest", "est"):
        chasse_c = sum(D["chasse_tot"][(ch, k)] for k in ks)
        tete = sum(val[(m["pseudo"], k)]["montant"] for m in D["membres"] if m["chaine"] == ch and m["pos"] == 1 for k in ks)
        gagne = sum(D["ext"][(ch, k)][0] for k in ks)
        perdu = sum(D["ext"][(ch, k)][1] for k in ks)
        goulot, pire = "", None
        for m in D["membres"]:  # le membre (hors chasseurs) le plus bas en % du chassé, s'il est sous le seuil
            if m["chaine"] != ch or m["type"] == "Chasseur":
                continue
            ps = [val[(m["pseudo"], k)].get("pct_chasse") for k in ks if val[(m["pseudo"], k)].get("pct_chasse") not in (None, "")]
            if ps:
                moyp = sum(ps) / len(ps)
                if moyp < SEUIL_NOEUD and (pire is None or moyp < pire):
                    pire, goulot = moyp, f"{m['pseudo']} (rang {m['pos']}, {round(moyp)} % du chassé)"
        r_chaine[ch] = len(L)
        L.append([f"chaîne {ch}", chasse_c, tete, pct(tete, chasse_c), goulot or "aucun", gagne, perdu, gagne - perdu])
        if chasse_c and pct(tete, chasse_c) != "" and pct(tete, chasse_c) < SEUIL_NOEUD:
            styles[(len(L) - 1, 3)] = "rouge"
        if goulot:
            styles[(len(L) - 1, 4)] = "rouge"
    L.append([])

    # --- origine du tdc de l'alliance
    d0, f1 = info[ks[0]]["d"], info[ks[-1]]["f"]
    croissance = D["al_tot"][f1] - D["al_tot"][d0]
    chasse_all = sum(D["chasse_tot"][(ch, k)] for ch in ("ouest", "est") for k in ks)
    net_ext = sum(D["ext"][(ch, k)][0] - D["ext"][(ch, k)][1] for ch in ("ouest", "est") for k in ks)
    oseil = sum(D["oseil"][k][0] - D["oseil"][k][1] for k in ks)
    IDX_ORIGINE = len(L)
    L.append(["3. ORIGINE DU TDC GAGNÉ PAR L'ALLIANCE"])
    L.append(["", "tdc", "% de la croissance"])
    L.append(["Croissance du tdc total", croissance, 100 if croissance else ""])
    L.append(["dont chasse (minimum)", chasse_all, pct(chasse_all, croissance)])
    L.append(["dont hors chasse (maximum = croissance − chasse)", max(croissance - chasse_all, 0), pct(max(croissance - chasse_all, 0), croissance)])
    L.append(["La part hors chasse est une fourchette : de la chasse masquée par une perte dans la même heure la réduit."])
    L.append([])

    # --- statistiques par joueur
    stats = {}
    for m in D["membres"]:
        n = m["pseudo"]
        ev = [k for k in ks if (n, k) in D["pos"]]
        if not ev:
            continue
        montants = [val[(n, k)]["montant"] for k in ev]
        moy = sum(montants) / len(ev)
        pcts = [val[(n, k)].get("pct_chasse") for k in ev if val[(n, k)].get("pct_chasse") not in (None, "")]
        inc = [val[(n, k)]["incertain"] for k in ev if val[(n, k)]["incertain"] != ""]
        hors = [val[(n, k)]["hors"] for k in ev if val[(n, k)]["hors"] != ""]
        actifs = [x for k in ev for x in val[(n, k)]["actifs"]]
        # tendance : seconde moitié de la plage contre première moitié ; pour 1 jour, contre la veille
        tendance = ""
        if len(ev) >= 2:
            h_ = len(ev) // 2
            a_, b_ = _moyenne([val[(n, k)]["montant"] for k in ev[:h_]]), _moyenne([val[(n, k)]["montant"] for k in ev[-h_:]])
        else:
            veille = [val[(n, k)]["montant"] for k in avant[-1:] if (n, k) in val]
            a_, b_ = (veille[0] if veille else None), moy
        if a_:
            r = b_ / a_ - 1
            tendance = "↑" if r > SEUIL_TENDANCE else "↓" if r < -SEUIL_TENDANCE else "→"
        # chasse vs habitude (chasseurs) : la plage contre les jours précédents ; sans jours précédents, le dernier jour contre le reste
        vs_hab = ""
        if m["type"] == "Chasseur":
            habitude = [val[(n, k)]["montant"] for k in habitude_ks if (n, k) in val]
            if habitude and _moyenne(habitude):
                vs_hab = round(100 * moy / _moyenne(habitude))
            elif len(ev) >= 3 and _moyenne([val[(n, k)]["montant"] for k in ev[:-1]]):
                vs_hab = round(100 * val[(n, ev[-1])]["montant"] / _moyenne([val[(n, k)]["montant"] for k in ev[:-1]]))
        stats[n] = dict(m=m, moy=moy, pct=round(sum(pcts) / len(pcts)) if pcts else "",
                        inc=round(sum(inc) / len(inc)) if inc else "", hors=round(sum(hors) / len(hors)) if hors else "",
                        pause=pause_max(actifs, info[ks[0]]["d"], info[ks[-1]]["f"]), tendance=tendance, vs_hab=vs_hab)
    for st in stats.values():
        m = st["m"]
        signaux = []
        if m["type"] != "Chasseur" and st["pct"] != "" and st["pct"] < SEUIL_NOEUD:
            signaux.append("ralentit la chaîne")
        if st["vs_hab"] != "" and st["vs_hab"] < SEUIL_HABITUDE:
            signaux.append("chasse en baisse")
        if st["inc"] != "" and st["inc"] > SEUIL_INCERTAIN:
            signaux.append("données fragiles")
        if st["hors"] != "" and st["hors"] > SEUIL_HORS:
            signaux.append("floods hors chaîne")
        st["signaux"] = signaux

    # --- à signaler
        # --- champions (insérés entre le bilan des chaînes et l'origine du tdc)
    def champion(type_, cle, meilleur):
        cand = [st for st in stats.values() if st["m"]["type"] == type_ and st[cle] not in ("", None)]
        return (max if meilleur else min)(cand, key=lambda st: st[cle]) if cand else None

    champs = [["2. CHAMPIONS"], ["catégorie", "joueur", "rôle · chaîne", "valeur", "détail"]]
    for label, typ, cle, meilleur in (("Meilleur chasseur", "Chasseur", "moy", True), ("Moins bon chasseur", "Chasseur", "moy", False),
                                      ("Meilleur passeur", "Passeur", "pct", True), ("Moins bon passeur", "Passeur", "pct", False)):
        st = champion(typ, cle, meilleur)
        if not st:
            champs.append([label, "—"])
        elif typ == "Chasseur":
            champs.append([label, st["m"]["pseudo"], f"{typ} · {st['m']['chaine']} {st['m']['pos']}", f"{fmt(round(st['moy']))} chassés / jour",
                           f"{st['pct']} % du chassé de la chaîne" if st["pct"] != "" else ""])
        else:
            champs.append([label, st["m"]["pseudo"], f"{typ} · {st['m']['chaine']} {st['m']['pos']}", f"{st['pct']} % du chassé",
                           f"{fmt(round(st['moy']))} envoyés / jour"])
    champs.append([])
    L[IDX_ORIGINE:IDX_ORIGINE] = champs

    L.append(["4. À SIGNALER"])
    L.append(["joueur", "rôle · chaîne", "signaux"])
    flagged = sorted((st for st in stats.values() if st["signaux"]), key=lambda st: (-len(st["signaux"]), st["pct"] if st["pct"] != "" else 999))
    for st in flagged:
        L.append([st["m"]["pseudo"], f"{st['m']['type']} · {st['m']['chaine']} {st['m']['pos']}", " ; ".join(st["signaux"])])
    if not flagged:
        L.append(["Aucun signal sur la plage"])
    L.append([])

    # --- tous les joueurs
    L.append(["5. TOUS LES JOUEURS"])
    L.append(["joueur", "rôle · chaîne", "moy. / jour", "% du chassé", "tendance",
              "chasse vs habitude (%)", "% incertain", "% hors chaîne", "pause max (h)", "signaux"])
    for ch in ("ouest", "est"):
        L.append([f"CHAÎNE {ch.upper()}"])
        for t in POSTES:
            for m in sorted((m for m in D["membres"] if m["type"] == t and m["chaine"] == ch), key=lambda m: m["pos"]):
                st = stats.get(m["pseudo"])
                if not st:
                    continue
                r = len(L)
                L.append([m["pseudo"], f"{t} · {ch} {m['pos']}", round(st["moy"]), st["pct"],
                          st["tendance"], st["vs_hab"], st["inc"], st["hors"], st["pause"], " ; ".join(st["signaux"])])
                if t != "Chasseur" and st["pct"] != "":
                    styles[(r, 3)] = "rouge" if st["pct"] < SEUIL_NOEUD else None
                if st["tendance"]:
                    styles[(r, 4)] = "vert" if st["tendance"] == "↑" else "rouge" if st["tendance"] == "↓" else None
                if st["vs_hab"] != "":
                    styles[(r, 5)] = "rouge" if st["vs_hab"] < SEUIL_HABITUDE else None
                if st["inc"] != "" and st["inc"] > SEUIL_INCERTAIN:
                    styles[(r, 6)] = "jaune"
                if st["hors"] != "" and st["hors"] > SEUIL_HORS:
                    styles[(r, 7)] = "orange"
    L.append([])
    L.append([f"Seuils : ralentit la chaîne < {SEUIL_NOEUD} % du chassé ; chasse en baisse < {SEUIL_HABITUDE} % de l'habitude ; "
              f"données fragiles > {SEUIL_INCERTAIN} % d'envois à cible incertaine ; floods hors chaîne (vers un joueur hors alliance, plus de {HORS_CHASSE} % du chassé du jour) > {SEUIL_HORS} % ; tendance ±{round(SEUIL_TENDANCE * 100)} % vs la plage précédente."])
    return L, styles
