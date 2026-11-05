"""Page HTML locale de synthèse, avec menu déroulant pour choisir la plage. Les données de tous les jours sont
embarquées dans la page ; le calcul de la synthèse se fait dans le navigateur. Aucune ressource externe."""
import json
import os

import feuilles as fe

SORTIE = os.environ.get("PAGE_SORTIE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "synthese.html")


def donnees(D, derniere_version, lignes_att):
    info, val = D["info"], D["val"]
    periodes = []
    for k, p in enumerate(info):
        e = dict(d=p["d"], f=p["f"], jour=p["jour"], heures=p["heures"], valide=p["valide"],
                 complet=p["valide"] and p["heures"] >= fe.JOUR_COMPLET, manquantes=D["manquantes"][k])
        if p["valide"]:
            e["croissance"] = D["al_tot"][p["f"]] - D["al_tot"][p["d"]]
            e["chasse"] = {ch: D["chasse_tot"][(ch, k)] for ch in ("ouest", "est")}
            e["tete"] = {ch: sum(val[(m["pseudo"], k)]["montant"] for m in D["membres"]
                                 if m["chaine"] == ch and m["pos"] == 1) for ch in ("ouest", "est")}
            e["ext"] = {ch: list(D["ext"][(ch, k)]) for ch in ("ouest", "est")}
            e["oseil"] = list(D["oseil"][k])
        periodes.append(e)
    membres, vals = [], {}
    for m in D["membres"]:
        n = m["pseudo"]
        membres.append(dict(pseudo=n, type=m["type"], chaine=m["chaine"], pos=m["pos"]))
        vals[n] = []
        for k in range(len(info)):
            v = val.get((n, k))
            vals[n].append(None if not v else dict(
                m=v["montant"], p=v.get("pct_chasse") if v.get("pct_chasse") != "" else None,
                i=v["incertain"] if v["incertain"] != "" else None, o=v["hors"] if v["hors"] != "" else None,
                h=v["heures"], a=v["actifs"], f=v["floods"]))
    seuils = dict(noeud=fe.SEUIL_NOEUD,
                  incertain=fe.SEUIL_INCERTAIN, hors=fe.SEUIL_HORS, horsChasse=fe.HORS_CHASSE, tendance=fe.SEUIL_TENDANCE, habitude=fe.SEUIL_HABITUDE)
    return dict(periodes=periodes, membres=membres, vals=vals, seuils=seuils, derniere=derniere_version)


def ecrire(lignes_att, D, derniere_version):
    data = json.dumps(donnees(D, derniere_version, lignes_att), ensure_ascii=False).replace("</", "<\\/")
    html = GABARIT.replace("__DONNEES__", data)
    os.makedirs(os.path.dirname(os.path.abspath(SORTIE)), exist_ok=True)
    tmp = SORTIE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)
    os.replace(tmp, SORTIE)


GABARIT = r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Synthèse Ambre</title>
<style>
:root{--bg:#f6f5f1;--carte:#fff;--texte:#22211f;--doux:#6b6962;--bord:#e2dfd7;--rouge:#b3261e;--rouge-bg:#fbe3e0;--jaune:#7a5b00;--jaune-bg:#fff0b8;--orange:#8c4600;--orange-bg:#ffd9aa;--vert:#1d6b3a;--vert-bg:#dff1e5;--accent:#8a5a1c;--barre:#d9a441}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#1b1a18;--carte:#25231f;--texte:#ece9e2;--doux:#a19d93;--bord:#38352f;--rouge:#ff9a90;--rouge-bg:#4a2320;--jaune:#f0d070;--jaune-bg:#4a3d10;--orange:#ffb870;--orange-bg:#573310;--vert:#8fd6a5;--vert-bg:#1f3a28;--accent:#e0b070;--barre:#c28a2c}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--texte);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:16px;margin:28px 0 10px;color:var(--accent);text-transform:uppercase;letter-spacing:.04em}
.sous{color:var(--doux);font-size:13px}
.barre{display:flex;flex-wrap:wrap;gap:12px;align-items:center;background:var(--carte);border:1px solid var(--bord);border-radius:10px;padding:12px 14px;margin:14px 0}
select,input[type=checkbox]{font:inherit}
select{padding:6px 8px;border-radius:6px;border:1px solid var(--bord);background:var(--bg);color:var(--texte)}
label{display:flex;gap:6px;align-items:center}
.cartes{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.carte{background:var(--carte);border:1px solid var(--bord);border-radius:10px;padding:12px 14px}
.carte h3{margin:0 0 6px;font-size:15px}
.chiffre{font-size:24px;font-weight:600}
table{border-collapse:collapse;width:100%;background:var(--carte);border:1px solid var(--bord);border-radius:10px;overflow:hidden}
.defil{overflow-x:auto}
th,td{padding:7px 10px;text-align:right;border-bottom:1px solid var(--bord);white-space:nowrap}
th{font-size:12px;color:var(--doux);font-weight:600;text-transform:uppercase;letter-spacing:.03em;background:var(--bg)}
th:first-child,td:first-child,td.g,th.g{text-align:left}
tr.titre td{background:var(--bg);font-weight:700;color:var(--accent);text-align:left}
td.rouge{background:var(--rouge-bg);color:var(--rouge);font-weight:600}
td.jaune{background:var(--jaune-bg);color:var(--jaune);font-weight:600}
td.orange{background:var(--orange-bg);color:var(--orange);font-weight:600}
td.vert{background:var(--vert-bg);color:var(--vert);font-weight:600}
tr.joueur{cursor:pointer}
tr.joueur:hover td{filter:brightness(.97)}
tr.detail td{background:var(--bg);white-space:normal;text-align:left;font-size:13px}
.puce{display:inline-block;border-radius:999px;padding:1px 9px;margin:1px 3px 1px 0;font-size:12px;background:var(--rouge-bg);color:var(--rouge)}
.puce.jaune{background:var(--jaune-bg);color:var(--jaune)}
.puce.orange{background:var(--orange-bg);color:var(--orange)}
.barreg{display:inline-block;height:8px;border-radius:4px;background:var(--barre);vertical-align:middle;margin-left:6px}
.note{color:var(--doux);font-size:12.5px;margin-top:8px}
.vide{color:var(--doux);font-style:italic}
</style>
</head>
<body>
<main>
<h1>Synthèse — alliance Ambre (serveur 5)</h1>
<div class="sous" id="meta"></div>
<div class="barre">
  <label>Plage
    <select id="plage">
      <option value="1">1 jour</option><option value="3" selected>3 jours</option><option value="7">7 jours</option>
      <option value="tout">Tout</option><option value="perso">Personnalisée…</option>
    </select></label>
  <span id="perso" hidden>
    <label>du <select id="debut"></select></label> <label>au <select id="fin"></select></label></span>
  <label><input type="checkbox" id="partiel"> inclure le jour en cours (partiel)</label>
</div>
<div id="etat" class="sous"></div>
<h2>1. Bilan des chaînes</h2><div class="cartes" id="chaines"></div>
<h2>2. Champions</h2><div class="cartes" id="champions"></div>
<h2>3. Origine du tdc gagné par l'alliance</h2><div id="origine"></div>
<h2>4. À signaler</h2><div id="signaler"></div>
<h2>5. Tous les joueurs <span class="sous" style="text-transform:none;letter-spacing:0">— cliquer sur un joueur pour voir ses floods jour par jour</span></h2>
<div class="defil" id="joueurs"></div>
<p class="note" id="seuils"></p>
</main>
<script>
const DATA = __DONNEES__;
const P = DATA.periodes, T = DATA.seuils;
const $ = id => document.getElementById(id);
const fmt = x => (x === null || x === undefined || x === "") ? "" : Math.round(x).toLocaleString("fr-FR");
const moy = a => a.length ? a.reduce((s, x) => s + x, 0) / a.length : null;
const somme = (a, f) => a.reduce((s, k) => s + f(k), 0);
const pct = (x, t) => t ? Math.round(100 * x / t) : null;
const esc = s => String(s).replace(/[&<>]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;"}[c]));
const POSTES = ["Grenier", "Passeur", "Chasseur"];
const puce = x => `<span class="puce${x === "données fragiles" ? " jaune" : x === "floods hors chaîne" ? " orange" : ""}">${x}</span>`;
const heure = v => Date.UTC(+v.slice(0, 4), +v.slice(4, 6) - 1, +v.slice(6, 8), +v.slice(8, 10), +v.slice(10, 12)) / 3.6e6;
const pauseMax = (acts, d, f) => { const t = [heure(d), ...acts.map(heure).sort((a, b) => a - b), heure(f)]; let m = 0; for (let i = 1; i < t.length; i++) m = Math.max(m, t[i] - t[i - 1]); return Math.round(m); };
const rolePos = m => `${m.type} · ${m.chaine} ${m.pos}`;

function indices() {
  const partiel = $("partiel").checked;
  const base = P.map((p, k) => k).filter(k => P[k].valide && (P[k].complet || partiel));
  let sel = $("plage").value, ks;
  if (sel === "perso") {
    const a = +$("debut").value, b = +$("fin").value;
    ks = base.filter(k => k >= Math.min(a, b) && k <= Math.max(a, b));
  } else {
    const n = sel === "tout" ? base.length : +sel;
    ks = base.slice(-n);
  }
  const N = ks.length;
  const avant = base.filter(k => k < ks[0]);
  const precedents = sel === "tout" ? [] : (avant.length >= Math.ceil(N / 2) ? avant.slice(-N) : []);
  return {base, ks, avant, precedents, N, sel};
}

function stats(ks, avant, precedents) {
  const st = {};
  for (const m of DATA.membres) {
    const v = DATA.vals[m.pseudo];
    const ev = ks.filter(k => v[k]);
    if (!ev.length) continue;
    const montants = ev.map(k => v[k].m), mm = moy(montants);
    const pcts = ev.map(k => v[k].p).filter(x => x !== null);
    const incs = ev.map(k => v[k].i).filter(x => x !== null), hors = ev.map(k => v[k].o).filter(x => x !== null);
    const acts = ev.flatMap(k => v[k].a);
    // tendance : seconde moitié de la plage contre la première ; pour 1 jour, contre la veille
    let tendance = "", A = null, B = mm;
    if (ev.length >= 2) {
      const h = Math.floor(ev.length / 2);
      A = moy(ev.slice(0, h).map(k => v[k].m)); B = moy(ev.slice(-h).map(k => v[k].m));
    } else {
      const veille = avant.slice(-1).filter(k => v[k]).map(k => v[k].m); A = veille.length ? veille[0] : null;
    }
    if (A) { const r = B / A - 1; tendance = r > T.tendance ? "↑" : r < -T.tendance ? "↓" : "→"; }
    // chasse vs habitude (chasseurs) : la plage contre les jours précédents ; sans jours précédents, le dernier jour contre le reste
    let vsHab = null;
    if (m.type === "Chasseur") {
      const hab = avant.filter(k => v[k]).map(k => v[k].m);
      if (hab.length && moy(hab)) vsHab = Math.round(100 * mm / moy(hab));
      else if (ev.length >= 3) { const reste = moy(ev.slice(0, -1).map(k => v[k].m)); if (reste) vsHab = Math.round(100 * v[ev[ev.length - 1]].m / reste); }
    }
    st[m.pseudo] = {m, moy: mm,
      pct: pcts.length ? Math.round(moy(pcts)) : null,
      inc: incs.length ? Math.round(moy(incs)) : null, hors: hors.length ? Math.round(moy(hors)) : null,
      pause: pauseMax(acts, P[ks[0]].d, P[ks[ks.length - 1]].f),
      tendance, vsHab, ev};
  }
  for (const s of Object.values(st)) {
    s.signaux = [];
    if (s.m.type !== "Chasseur" && s.pct !== null && s.pct < T.noeud) s.signaux.push("retient le flux");
    if (s.vsHab !== null && s.vsHab < T.habitude) s.signaux.push("chasse en baisse");
    if (s.inc !== null && s.inc > T.incertain) s.signaux.push("données fragiles");
    if (s.hors !== null && s.hors > T.hors) s.signaux.push("floods hors chaîne");
  }
  return {st};
}

function rendre() {
  const {base, ks, avant, precedents, N} = indices();
  $("meta").textContent = "Données jusqu'au relevé du " + DATA.derniere;
  if (!ks.length) { $("etat").textContent = "Pas encore de jour complet."; return; }
  const jours = ks.map(k => P[k].jour);
  const manque = somme(ks, k => P[k].manquantes);
  $("etat").innerHTML = `<b>${ks.length} jour${ks.length > 1 ? "s" : ""}</b> : ${jours[0]}${ks.length > 1 ? " → " + jours[jours.length - 1] : ""}. ` +
    (manque ? `${manque} h manquantes (versions non publiées par l'API) : montants regroupés. ` : "Données complètes. ") +
    "Jours UTC.";
  const {st} = stats(ks, avant, precedents);
  const stList = Object.values(st);

  // 1. chaînes
  let h = "";
  for (const ch of ["ouest", "est"]) {
    const chasse = somme(ks, k => P[k].chasse[ch]), tete = somme(ks, k => P[k].tete[ch]);
    const g = somme(ks, k => P[k].ext[ch][0]), p = somme(ks, k => P[k].ext[ch][1]);
    let goulot = null;
    for (const s of stList) {
      if (s.m.chaine !== ch || s.m.type === "Chasseur" || s.pct === null) continue;
      if (s.pct < T.noeud && (!goulot || s.pct < goulot.pct)) goulot = s;
    }
    const pt = pct(tete, chasse);
    h += `<div class="carte"><h3>Chaîne ${ch}</h3>
      <div class="chiffre">${fmt(chasse)} <span class="sous">chassé</span></div>
      <div>Reçu par le grenier de tête : <b>${fmt(tete)}</b> (${pt ?? "–"} % du chassé)</div>
      <div>Goulot : ${goulot ? `<span class="puce">${esc(goulot.m.pseudo)} · rang ${goulot.m.pos} · ${goulot.pct} % du chassé</span>` : "<b>aucun</b>"}</div>
      <div class="sous">Extérieur : +${fmt(g)} / −${fmt(p)} = <b>${fmt(g - p)}</b></div></div>`;
  }
  $("chaines").innerHTML = h;

  // champions : chasseurs sur le tdc chassé par jour ; passeurs sur le % du chassé de leur chaîne
  const champ = (typ, cle, meilleur) => {
    const c = stList.filter(s => s.m.type === typ && s[cle] !== null && s[cle] !== undefined);
    if (!c.length) return null;
    return c.reduce((a, b) => (meilleur ? b[cle] > a[cle] : b[cle] < a[cle]) ? b : a);
  };
  const carteChamp = (titre, s, typ) => !s ? `<div class="carte"><h3>${titre}</h3><span class="vide">—</span></div>` :
    `<div class="carte"><h3>${titre}</h3><div class="chiffre">${esc(s.m.pseudo)}</div>
      <div class="sous">${esc(s.m.type)} · chaîne ${s.m.chaine} · rang ${s.m.pos}</div>
      <div>${typ === "Chasseur" ? `<b>${fmt(s.moy)}</b> chassés / jour${s.pct !== null ? ` (${s.pct} % du chassé de la chaîne)` : ""}`
        : `<b>${s.pct} %</b> du chassé de la chaîne (${fmt(s.moy)} envoyés / jour)`}</div></div>`;
  $("champions").innerHTML = carteChamp("🏆 Meilleur chasseur", champ("Chasseur", "moy", true), "Chasseur") +
    carteChamp("Moins bon chasseur", champ("Chasseur", "moy", false), "Chasseur") +
    carteChamp("🏆 Meilleur passeur", champ("Passeur", "pct", true), "Passeur") +
    carteChamp("Moins bon passeur", champ("Passeur", "pct", false), "Passeur");

  // 3. origine du tdc
  const d0 = ks[0], f1 = ks[ks.length - 1];
  const croissance = somme(ks, k => P[k].croissance);
  const chasseAll = somme(ks, k => P[k].chasse.ouest + P[k].chasse.est);
  const ligne = (lib, x, ind = false) => `<tr><td${ind ? ' style="padding-left:28px"' : ""}>${lib}</td><td>${fmt(x)}</td><td>${pct(x, croissance) ?? ""}${croissance ? " %" : ""}
    <span class="barreg" style="width:${Math.max(0, Math.min(100, pct(x, croissance) || 0)) * 1.2}px"></span></td></tr>`;
  $("origine").innerHTML = `<table><tr><th></th><th>tdc</th><th>% de la croissance</th></tr>` +
    ligne("Croissance du tdc total", croissance) + ligne("dont chasse (minimum)", chasseAll) +
    ligne("dont hors chasse (maximum = croissance − chasse)", Math.max(croissance - chasseAll, 0)) +
    `</table><p class="note">La part hors chasse est une fourchette : de la chasse masquée par une perte dans la même heure la réduit.</p>`;

  // 3. à signaler
  const flag = stList.filter(s => s.signaux.length).sort((a, b) => b.signaux.length - a.signaux.length || (a.pct ?? 999) - (b.pct ?? 999));
  $("signaler").innerHTML = flag.length ? `<table><tr><th>Joueur</th><th class="g">Rôle · chaîne</th><th class="g">Signaux</th></tr>` +
    flag.map(s => `<tr><td>${esc(s.m.pseudo)}</td><td class="g">${esc(rolePos(s.m))}</td><td class="g">${s.signaux.map(puce).join("")}</td></tr>`).join("") + "</table>"
    : `<p class="vide">Aucun signal sur la plage.</p>`;

  // 4. tous les joueurs
  const cl = (c) => c ? ` class="${c}"` : "";
  let t = `<table><tr><th>Joueur</th><th class="g">Rôle · chaîne</th><th>Moy. / jour</th><th>% du chassé</th><th>Tendance</th><th>Chasse vs habitude</th><th>% incertain</th><th>% hors chaîne</th><th>Pause max (h)</th><th class="g">Signaux</th></tr>`;
  for (const ch of ["ouest", "est"]) {
    t += `<tr class="titre"><td colspan="12">Chaîne ${ch}</td></tr>`;
    for (const typ of POSTES) {
      for (const m of DATA.membres.filter(m => m.type === typ && m.chaine === ch).sort((a, b) => a.pos - b.pos)) {
        const s = st[m.pseudo]; if (!s) continue;
        const c1 = "";
        const c2 = (typ !== "Chasseur" && s.pct !== null && s.pct < T.noeud) ? "rouge" : "";
        const c4 = s.tendance === "↑" ? "vert" : s.tendance === "↓" ? "rouge" : "";
        const c5 = (s.vsHab !== null && s.vsHab < T.habitude) ? "rouge" : "";
        const c6 = (s.inc !== null && s.inc > T.incertain) ? "jaune" : "", c7 = (s.hors !== null && s.hors > T.hors) ? "orange" : "";
        t += `<tr class="joueur" data-n="${esc(m.pseudo)}"><td>${esc(m.pseudo)}</td><td class="g">${esc(m.type)} · ${m.pos}</td>
          <td${cl(c1)}>${fmt(s.moy)}</td><td${cl(c2)}>${s.pct ?? ""}${s.pct !== null ? " %" : ""}</td>
          <td${cl(c4)}>${s.tendance}</td><td${cl(c5)}>${s.vsHab !== null ? s.vsHab + " %" : ""}</td><td${cl(c6)}>${s.inc !== null ? s.inc + " %" : ""}</td><td${cl(c7)}>${s.hors !== null ? s.hors + " %" : ""}</td><td>${s.pause}</td>
          <td class="g">${s.signaux.map(puce).join("")}</td></tr>`;
      }
    }
  }
  $("joueurs").innerHTML = t + "</table>";
  document.querySelectorAll("tr.joueur").forEach(tr => tr.addEventListener("click", () => {
    const nxt = tr.nextElementSibling;
    if (nxt && nxt.classList.contains("detail")) { nxt.remove(); return; }
    const s = st[tr.dataset.n], v = DATA.vals[tr.dataset.n];
    const corps = s.ev.map(k => `<div><b>${P[k].jour}</b> — ${fmt(v[k].m)}${v[k].p !== null ? ` (${v[k].p} % du chassé)` : ""}${v[k].o !== null && v[k].o > 0 ? `, ${v[k].o} % hors chaîne` : ""}${v[k].i !== null && v[k].i > 0 ? `, ${v[k].i} % incertain` : ""}<br>${esc(v[k].f) || "<span class=vide>aucun flood</span>"}</div>`).join("");
    const d = document.createElement("tr"); d.className = "detail";
    d.innerHTML = `<td colspan="12">${corps}</td>`; tr.after(d);
  }));
  $("seuils").textContent = `Seuils : retient le flux < ${T.noeud} % du chassé ; chasse en baisse < ${T.habitude} % de l'habitude ; données fragiles > ${T.incertain} % d'envois à cible incertaine ; floods hors chaîne (vers un joueur hors alliance, plus de ${T.horsChasse} % du chassé du jour) > ${T.hors} % ; ` +
    `tendance ±${Math.round(T.tendance * 100)} % vs la plage précédente. Tout est comparé au tdc chassé de la chaîne. Tendance : seconde moitié de la plage contre la première (1 jour : contre la veille). Chasse vs habitude : la plage contre les jours précédents (sinon dernier jour contre le reste). Jaune = données fragiles (cibles incertaines), orange = floods hors chaîne. « Pause max » : plus longue période sans activité (flood lancé ; chasseurs : chasse qui progresse).`;
}

function remplirDates() {
  const base = P.map((p, k) => k).filter(k => P[k].valide && (P[k].complet || $("partiel").checked));
  for (const id of ["debut", "fin"]) {
    const cur = $(id).value;
    $(id).innerHTML = base.map(k => `<option value="${k}">${P[k].jour}</option>`).join("");
    if (cur) $(id).value = cur;
  }
  if (!$("debut").value || !$("fin").value) { $("debut").value = base[0]; $("fin").value = base[base.length - 1]; }
}
$("plage").addEventListener("change", () => { $("perso").hidden = $("plage").value !== "perso"; rendre(); });
for (const id of ["debut", "fin"]) $(id).addEventListener("change", rendre);
$("partiel").addEventListener("change", () => { remplirDates(); rendre(); });
remplirDates(); rendre();
</script>
</body>
</html>
"""
