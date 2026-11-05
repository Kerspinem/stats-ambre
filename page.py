"""Page HTML de synthèse. Les données horaires (une entrée par relevé) sont embarquées dans la page ; le navigateur
calcule la synthèse pour la plage choisie (24 h, aujourd'hui, hier, 3 jours, 7 jours, tout, dates libres).
Aucune ressource externe."""
import json
import os
from datetime import datetime

import collect
import feuilles as fe

SORTIE = os.environ.get("PAGE_SORTIE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "synthese.html")


def _dt(v):
    return datetime.strptime(v, "%Y%m%d%H%M")


def donnees(D, lignes_att):
    roles = D["roles"]
    pl = collect.lire(collect.CSV_PL)[1:]
    versions = sorted({r[0] for r in pl})
    idx = {v: i for i, v in enumerate(versions)}  # étape i (i >= 1) : intervalle (versions[i-1], versions[i]]
    n = len(versions)
    membres = D["membres"]
    noms = [m["pseudo"] for m in membres]
    pos = {m["pseudo"]: m for m in membres}

    steps = [{"v": versions[i], "h": max(1, round((_dt(versions[i]) - _dt(versions[i - 1])).total_seconds() / 3600))}
             for i in range(1, n)]
    z = lambda: [0] * (n - 1)
    s, c, p, o = ({nom: z() for nom in noms} for _ in range(4))
    # chasse : gains horaires positifs des chasseurs
    for r in pl:
        if r[3] in c and r[6] != "" and int(r[6]) > 0 and roles[r[3]]["type"] == "Chasseur" and r[0] in idx and idx[r[0]] >= 1:
            c[r[3]][idx[r[0]] - 1] += int(r[6])
    # seuil « hors chaîne » : 5 % du tdc chassé par jour de la chaîne (moyenne des jours complets récents)
    seuil = {}
    for ch in ("ouest", "est"):
        ks = [k for k, pp in enumerate(D["info"]) if pp["valide"] and pp["heures"] >= fe.JOUR_COMPLET][-7:]
        mean = sum(D["chasse_tot"][(ch, k)] for k in ks) / len(ks) if ks else 0
        seuil[ch] = fe.HORS_CHASSE / 100 * mean
    chaine = {ch: {k: z() for k in ("chasse", "tete", "extg", "extp")} for ch in ("ouest", "est")}
    att = []
    CODE = {"certain": 0, "plausible": 1, "hors chaîne": 2, "externe": 3}
    for a in lignes_att:
        if a[0] not in idx or idx[a[0]] < 1:
            continue
        i = idx[a[0]] - 1
        att.append([i, a[2], a[3], a[4], CODE.get(a[5], 0)])
        if a[2] in s:
            s[a[2]][i] += a[4]
            if a[5] == "plausible":
                p[a[2]][i] += a[4]
            if a[3] not in roles and a[4] > seuil[pos[a[2]]["chaine"]]:
                o[a[2]][i] += a[4]
            if a[3] not in roles:
                chaine[pos[a[2]]["chaine"]]["extg"][i] += a[4]
        if a[3] in s and a[2] not in roles:
            chaine[pos[a[3]]["chaine"]]["extp"][i] += a[4]
    for nom in noms:
        ch = pos[nom]["chaine"]
        for i in range(n - 1):
            chaine[ch]["chasse"][i] += c[nom][i]
            if pos[nom]["pos"] == 1:
                chaine[ch]["tete"][i] += s[nom][i]
    # totaux d'alliance par relevé
    al = {r[0]: r for r in collect.lire(collect.CSV_AL)[1:]}
    num = lambda r, k: int(r[k]) if len(r) > k and r[k] != "" else None
    totaux = [{"tdc": num(al[v], 2) if v in al else None, "mem": num(al[v], 6) if v in al else None,
               "fou": num(al[v], 7) if v in al else None, "tec": num(al[v], 8) if v in al else None,
               "tro": num(al[v], 9) if v in al else None} for v in versions]
    # tdc de chaque joueur à chaque relevé, et positions (pour le schéma)
    tdc = {nom: [0] * n for nom in noms}
    for r in pl:
        if r[3] in tdc and r[0] in idx:
            tdc[r[3]][idx[r[0]]] = int(r[5])
    try:
        positions = json.load(open(collect.STATE)).get("pos", {})
    except Exception:
        positions = {}
    return dict(steps=steps, first=versions[0], al=totaux, tdc=tdc, pos=positions,
                membres=[dict(pseudo=m["pseudo"], type=m["type"], chaine=m["chaine"], pos=m["pos"]) for m in membres],
                s=s, c=c, p=p, o=o, chaine=chaine, att=att,
                seuils=dict(noeud=fe.SEUIL_NOEUD, incertain=fe.SEUIL_INCERTAIN, hors=fe.SEUIL_HORS,
                            horsChasse=fe.HORS_CHASSE, tendance=fe.SEUIL_TENDANCE, habitude=fe.SEUIL_HABITUDE))


def ecrire(lignes_att, D, derniere_version=None):
    data = json.dumps(donnees(D, lignes_att), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
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
select,input{font:inherit}
select,input[type=date]{padding:6px 8px;border-radius:6px;border:1px solid var(--bord);background:var(--bg);color:var(--texte)}
label{display:flex;gap:6px;align-items:center}
.cartes{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.carte{background:var(--carte);border:1px solid var(--bord);border-radius:10px;padding:12px 14px}
.carte h3{margin:0 0 6px;font-size:13px;color:var(--doux);text-transform:uppercase;letter-spacing:.04em}
.chiffre{font-size:24px;font-weight:600}
.delta{font-size:13px;font-weight:600;margin-top:2px}
.delta.plus{color:var(--vert)}.delta.moins{color:var(--rouge)}.delta.nul{color:var(--doux)}
table{border-collapse:collapse;width:100%;background:var(--carte);border:1px solid var(--bord);border-radius:10px;overflow:hidden}
.tj{table-layout:auto}
.tj th,.tj td{white-space:normal;padding:8px 7px;font-size:15px;line-height:1.3}
.tj th{font-size:12px}
.tj .puce{font-size:12px;padding:1px 8px}
.tj td:first-child .sous{font-size:12px}
@media (max-width:560px){.tj .opt{display:none}}
@media (max-width:640px){main{padding:14px 8px 40px}.tj th,.tj td{padding:6px 4px;font-size:13px}.tj th{font-size:10.5px}.tj .puce{font-size:11px;padding:0 6px}}
th,td{padding:7px 10px;text-align:right;border-bottom:1px solid var(--bord)}
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
.sch{width:100%;height:auto;display:block}
.sch text{font-family:inherit;fill:var(--texte)}
.sch .axe{fill:var(--doux);font-size:2.3px}
.legende{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:10px;font-size:13px;color:var(--doux)}
.legende i{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:5px;vertical-align:-1px}
.fl{font-size:1.25em;font-weight:700}
.fl.vert{color:var(--vert)}.fl.rouge{color:var(--rouge)}
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
      <option value="24" selected>24 h</option><option value="aujourdhui">Aujourd'hui</option><option value="hier">Hier</option>
      <option value="72">3 jours</option><option value="168">7 jours</option><option value="tout">Tout</option>
      <option value="perso">Personnalisée…</option>
    </select></label>
  <span id="perso" hidden>
    <label>du <input type="date" id="debut"></label> <label>au <input type="date" id="fin"></label></span>
</div>
<div id="etat" class="sous"></div>
<h2>1. Bilan alliance</h2><div class="kpis" id="bilan"></div><div id="origine" style="margin-top:14px"></div>
<h2>2. Bilan des chaînes</h2><div class="cartes" id="chaines"></div><div class="carte" id="schema" style="margin-top:12px"></div>
<h2>3. Champions</h2><div class="cartes" id="champions"></div>
<h2>4. À signaler</h2><div id="signaler"></div>
<h2>5. Tous les joueurs <span class="sous" style="text-transform:none;letter-spacing:0">— cliquer sur un joueur pour voir ses floods</span></h2>
<div id="joueurs"></div>
<p class="note" id="seuils"></p>
</main>
<script>
const DATA = __DONNEES__;
const T = DATA.seuils, S = DATA.steps.map(x => ({...x, t: tms(x.v)})), AL = DATA.al.map((x, i) => ({...x, t: tms(i ? S[i - 1].v : DATA.first)}));
function tms(v) { return Date.UTC(+v.slice(0, 4), +v.slice(4, 6) - 1, +v.slice(6, 8), +v.slice(8, 10), +v.slice(10, 12)); }
const $ = id => document.getElementById(id);
const fmt = x => (x === null || x === undefined || x === "") ? "—" : Math.round(x).toLocaleString("fr-FR");
const sgn = x => (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(Math.round(x)).toLocaleString("fr-FR");
const somme = (a, f) => a.reduce((s, i) => s + f(i), 0);
const pct = (x, t) => t ? Math.round(100 * x / t) : null;
const esc = s => String(s).replace(/[&<>]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;"}[c]));
const H = 3600e3, POSTES = ["Grenier", "Passeur", "Chasseur"];
const rolePos = m => `${m.type} · ${m.chaine} ${m.pos}`;
const PARIS = new Intl.DateTimeFormat("fr-CA", {timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", hourCycle: "h23"});
const quand = ms => new Intl.DateTimeFormat("fr-FR", {timeZone: "Europe/Paris", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"}).format(new Date(ms));
const jourParis = ms => PARIS.format(new Date(ms)).slice(0, 10);
function minuitParis(ms) {  // dernier minuit à Paris <= ms
  const j = jourParis(ms), [y, m, d] = j.split("-").map(Number);
  for (const off of [2, 1, 0]) { const c = Date.UTC(y, m - 1, d, 0) - off * H; if (jourParis(c) === j && PARIS.format(new Date(c)).slice(11, 13) === "00") return c; }
  return Date.UTC(y, m - 1, d) - H;
}
const minuitDe = j => { const [y, m, d] = j.split("-").map(Number); return minuitParis(Date.UTC(y, m - 1, d, 12)); };

function fenetre() {
  const fin = S[S.length - 1].t, debutData = S[0].t - S[0].h * H, sel = $("plage").value;
  let t0, t1 = fin;
  if (sel === "aujourdhui") t0 = minuitParis(fin);
  else if (sel === "hier") { t1 = minuitParis(fin); t0 = minuitParis(t1 - 1); }
  else if (sel === "tout") t0 = debutData;
  else if (sel === "perso") {
    if (!$("debut").value || !$("fin").value) return null;
    t0 = minuitDe($("debut").value); t1 = Math.min(minuitDe($("fin").value) + 24 * H, fin);
  } else t0 = fin - (+sel) * H;
  t0 = Math.max(t0, debutData);
  const idx = S.map((s, i) => i).filter(i => S[i].t > t0 && S[i].t <= t1);
  return {t0, t1, idx, heures: somme(idx, i => S[i].h), debutData};
}

const rate = (idx, f) => { const h = somme(idx, i => S[i].h); return h ? somme(idx, f) / h : null; };

function stats(W) {
  const {idx, heures} = W, st = {}, ch = {};
  for (const c of ["ouest", "est"]) ch[c] = {chasse: somme(idx, i => DATA.chaine[c].chasse[i]), tete: somme(idx, i => DATA.chaine[c].tete[i]),
    extg: somme(idx, i => DATA.chaine[c].extg[i]), extp: somme(idx, i => DATA.chaine[c].extp[i])};
  const avant = S.map((s, i) => i).filter(i => S[i].t <= W.t0);
  const hAvant = somme(avant, i => S[i].h);
  const mid = W.t0 + (W.t1 - W.t0) / 2;
  for (const m of DATA.membres) {
    const n = m.pseudo, chass = m.type === "Chasseur";
    const montant = i => chass ? DATA.c[n][i] : DATA.s[n][i];
    const tot = somme(idx, montant), sent = somme(idx, i => DATA.s[n][i]);
    const moy = heures ? tot / heures * 24 : 0;
    const pc = pct(tot, ch[m.chaine].chasse);
    const inc = (!chass && sent) ? Math.round(100 * somme(idx, i => DATA.p[n][i]) / sent) : null;
    const hors = (!chass && sent) ? Math.round(100 * somme(idx, i => DATA.o[n][i]) / sent) : null;
    // pause max : plus longue période sans activité dans la fenêtre
    const act = idx.filter(i => montant(i) > 0).map(i => S[i].t).sort((a, b) => a - b);
    const pts = [W.t0, ...act, W.t1]; let pause = 0;
    for (let k = 1; k < pts.length; k++) pause = Math.max(pause, pts[k] - pts[k - 1]);
    // tendance : la plage contre les 48 h qui la précèdent (flèche seule) ; nécessite au moins 24 h de recul
    let tendance = "", ratio = null;
    const prec = S.map((s, i) => i).filter(i => S[i].t > W.t0 - 48 * H && S[i].t <= W.t0);
    if (somme(prec, i => S[i].h) >= 24) {
      const A = rate(prec, montant), B = rate(idx, montant);
      if (A) { ratio = B / A; tendance = ratio - 1 > T.tendance ? "↑" : ratio - 1 < -T.tendance ? "↓" : "→"; }
    }
    const s = {m, moy, tot, pct: pc, inc, hors, pause: Math.round(pause / H), tendance, ratio, signaux: []};
    if (!chass && pc !== null && pc < T.noeud) s.signaux.push("ralentit la chaîne");
    if (ratio !== null && 100 * ratio < T.habitude) s.signaux.push("perf en baisse");
    if (inc !== null && inc > T.incertain) s.signaux.push("données fragiles");
    if (hors !== null && hors > T.hors) s.signaux.push("floods hors chaîne");
    st[n] = s;
  }
  return {st, ch};
}

const puce = x => `<span class="puce${x === "données fragiles" ? " jaune" : x === "floods hors chaîne" ? " orange" : ""}">${x}</span>`;

function schema(W) {
  const i1 = W.idx[W.idx.length - 1], set = new Set(W.idx);
  const mem = DATA.membres.filter(m => DATA.pos[m.pseudo]);
  if (!mem.length) { $("schema").innerHTML = '<span class="vide">Positions des joueurs indisponibles pour le moment.</span>'; return; }
  const tdc = n => DATA.tdc[n][i1 + 1] || 0, tmax = Math.max(...mem.map(m => tdc(m.pseudo)), 1);
  const R = n => 0.9 + 3.0 * Math.sqrt(tdc(n) / tmax);
  const XY = n => DATA.pos[n];
  const flux = {};
  for (const [i, a, c, x] of DATA.att) if (set.has(i)) flux[a + ">" + c] = (flux[a + ">" + c] || 0) + x;
  const COL = {Grenier: "#2f9e4f", Passeur: "#1f78d1", Chasseur: "#d64545"};
  const edges = [];
  for (const ch of ["ouest", "est"]) {
    const ms = mem.filter(m => m.chaine === ch);
    for (const a of ms) for (const b of ms) if (b.pos === a.pos + 1) edges.push({a, b, f: flux[a.pseudo + ">" + b.pseudo] || 0});
  }
  const fmax = Math.max(...edges.map(e => e.f), 1);
  let fl = "", traits = "", pills = "", nodes = "", grille = "";
  for (let v = 0; v <= 100; v += 10) {
    grille += `<text class="axe" x="${v}" y="-3.5" text-anchor="middle">${v}</text><text class="axe" x="-5" y="${v + 0.8}" text-anchor="end">${v}</text>`;
    for (let w = 0; w <= 70; w += 10) grille += `<circle cx="${v}" cy="${w}" r="0.35" fill="var(--bord)"/>`;
  }
  for (const e of edges) {
    const [x1, y1] = XY(e.a.pseudo), [x2, y2] = XY(e.b.pseudo), r1 = R(e.a.pseudo), r2 = R(e.b.pseudo);
    const dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy) || 1, ux = dx / L, uy = dy / L, nx = -uy, ny = ux;
    const couleur = e.b.type === "Chasseur" ? COL.Chasseur : e.a.type === "Grenier" ? COL.Grenier : COL.Passeur;
    if (e.f === 0) continue;  // pas de flux sur la plage : pas de flèche
    const rouge = e.b.type === "Chasseur", w = rouge ? 0.45 : 0.8;  // flèche toujours identique, plus fine vers les chasseurs
    const titre0 = `<title>${esc(e.a.pseudo)} → ${esc(e.b.pseudo)} : ${fmt(e.f)} sur la plage</title>`;
    if (L < r1 + r2 + 3.5) {  // trop proches : un simple trait au lieu d'une flèche
      traits += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${couleur}" stroke-width="${w}" stroke-linecap="round">${titre0}</line>`;
      continue;
    }
    const s = [x1 + ux * (r1 + 0.6), y1 + uy * (r1 + 0.6)], en = [x2 - ux * (r2 + 0.6), y2 - uy * (r2 + 0.6)];
    const hl = rouge ? 1.5 : 2.0, hw = rouge ? 0.85 : 1.25, b = [en[0] - ux * hl, en[1] - uy * hl];
    const pt = (q, k) => `${(q[0] + nx * k).toFixed(2)},${(q[1] + ny * k).toFixed(2)}`;
    const titre = `<title>${esc(e.a.pseudo)} → ${esc(e.b.pseudo)} : ${fmt(e.f)} sur la plage</title>`;
    fl += `<polygon points="${pt(s, w / 2)} ${pt(b, w / 2)} ${pt(b, hw)} ${en[0].toFixed(2)},${en[1].toFixed(2)} ${pt(b, -hw)} ${pt(b, -w / 2)} ${pt(s, -w / 2)}" fill="${couleur}">${titre}</polygon>`;
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2, d = String(Math.round(L)), pw = 2.6 + 1.25 * d.length;
    pills += `<rect x="${(mx - pw / 2).toFixed(2)}" y="${(my - 1.5).toFixed(2)}" width="${pw}" height="3" rx="1.5" fill="var(--carte)" stroke="${couleur}" stroke-width="0.25"/>
      <text x="${mx.toFixed(2)}" y="${(my + 0.9).toFixed(2)}" text-anchor="middle" style="font-size:2.3px">${d}</text>`;
  }
  const boites = [], pts = mem.map(m => ({x: XY(m.pseudo)[0], y: XY(m.pseudo)[1], r: R(m.pseudo)}));
  const libre = q => q.x >= -9 && q.x + q.w <= 115 && !boites.some(o => q.x < o.x + o.w && q.x + q.w > o.x && q.y < o.y + 3.4 && q.y + 3.4 > o.y) &&
    !pts.some(o => q.x < o.x + o.r && q.x + q.w > o.x - o.r && q.y < o.y + o.r && q.y + 3.4 > o.y - o.r);
  for (const m of [...mem].sort((a, b) => XY(a.pseudo)[1] - XY(b.pseudo)[1])) {
    const [x, y] = XY(m.pseudo), r = R(m.pseudo), c = COL[m.type], largeur = 1.7 * m.pseudo.length + 2.2;
    const D = r + 0.8, dr = {x: x + D, y: y - 1.7, w: largeur}, ga = {x: x - D - largeur, y: y - 1.7, w: largeur};
    const cand = (x > 80 ? [ga, dr] : [dr, ga]).concat([{x: dr.x, y: y + 1.5, w: largeur}, {x: dr.x, y: y - 4.9, w: largeur},
      {x: ga.x, y: y + 1.5, w: largeur}, {x: ga.x, y: y - 4.9, w: largeur}, {x: x - largeur / 2, y: y + r + 0.8, w: largeur},
      {x: x - largeur / 2, y: y - r - 4.2, w: largeur}, {x: dr.x, y: y + 4.9, w: largeur}, {x: ga.x, y: y + 4.9, w: largeur}]);
    const ch = cand.find(libre) || cand[0], bx = ch.x, by = ch.y;
    boites.push({x: bx, y: by, w: largeur});
    nodes += `<g><circle cx="${x}" cy="${y}" r="${(r * 1.85).toFixed(2)}" fill="${c}" opacity=".16"/>
      <circle cx="${x}" cy="${y}" r="${r.toFixed(2)}" fill="${c}" stroke="#fff" stroke-width="0.5"><title>${esc(m.pseudo)} — tdc ${fmt(tdc(m.pseudo))}</title></circle>
      <rect x="${bx.toFixed(2)}" y="${by.toFixed(2)}" width="${largeur.toFixed(2)}" height="3.4" rx="0.9" fill="var(--carte)" stroke="${c}" stroke-width="0.3"/>
      <text x="${(bx + largeur / 2).toFixed(2)}" y="${(by + 2.45).toFixed(2)}" text-anchor="middle" style="font-size:2.5px;font-weight:600">${esc(m.pseudo)}</text></g>`;
  }
  $("schema").innerHTML = `<svg class="sch" viewBox="-10 -7 126 80" role="img" aria-label="Schéma des chaînes">${grille}${fl}${pills}${nodes}${traits}</svg>
    <div class="legende"><span><i style="background:${COL.Grenier}"></i>Grenier</span><span><i style="background:${COL.Passeur}"></i>Passeur</span>
    <span><i style="background:${COL.Chasseur}"></i>Chasseur</span><span>Taille du point : tdc au ${quand(S[i1].t)}</span>
    <span>Flèche : tdc pris sur la plage (pas de flèche : aucun flux)</span><span>Pastille : distance en cases (trait simple si les joueurs sont trop proches)</span></div>`;
}

function rendre() {
  const W = fenetre();
  $("meta").textContent = "Données jusqu'au relevé du " + quand(S[S.length - 1].t) + " (heure de Paris)";
  if (!W || !W.idx.length) { $("etat").textContent = "Aucune donnée sur cette plage."; for (const id of ["bilan", "chaines", "champions", "origine", "signaler", "joueurs"]) $(id).innerHTML = ""; return; }
  const manque = somme(W.idx, i => S[i].h - 1);
  $("etat").innerHTML = `<b>${Math.round(W.heures)} h</b> de données : du ${quand(W.t0)} au ${quand(W.t1)} (heure de Paris). ` +
    (manque ? `${manque} h manquantes (versions non publiées par l'API) : montants regroupés.` : "Données complètes.");
  const {st, ch} = stats(W);
  const stList = Object.values(st);
  const i0 = W.idx[0], i1 = W.idx[W.idx.length - 1], dep = AL[i0], arr = AL[i1 + 1];

  // bilan alliance : valeur à la fin de la plage et variation sur la plage
  const kpi = (lib, v, d, fmtv = fmt) => `<div class="carte"><h3>${lib}</h3><div class="chiffre">${v === null || v === undefined ? "—" : fmtv(v)}</div>
    <div class="delta ${d > 0 ? "plus" : d < 0 ? "moins" : "nul"}">${d === null || d === undefined ? "" : (d === 0 ? "=" : sgn(d)) + " sur la plage"}</div></div>`;
  const dlt = k => (arr[k] !== null && dep[k] !== null) ? arr[k] - dep[k] : null;
  const pm = a => (a.tdc !== null && a.mem) ? a.tdc / a.mem : null;
  $("bilan").innerHTML = kpi("Membres", arr.mem, dlt("mem")) + kpi("TDC", arr.tdc, dlt("tdc")) +
    kpi("TDC / membre", pm(arr), (pm(arr) !== null && pm(dep) !== null) ? pm(arr) - pm(dep) : null) +
    kpi("Fourmilière", arr.fou, dlt("fou")) + kpi("Techno", arr.tec, dlt("tec")) + kpi("Trophées", arr.tro, dlt("tro"));

  // 1. chaînes
  let h = "";
  for (const c of ["ouest", "est"]) {
    const x = ch[c];
    let goulot = null;
    for (const s of stList) { if (s.m.chaine !== c || s.m.type === "Chasseur" || s.pct === null) continue; if (s.pct < T.noeud && (!goulot || s.pct < goulot.pct)) goulot = s; }
    h += `<div class="carte"><h3>Chaîne ${c}</h3><div class="chiffre">${fmt(x.chasse)} <span class="sous">chassé</span></div>
      <div>Reçu par le grenier de tête : <b>${fmt(x.tete)}</b> (${pct(x.tete, x.chasse) ?? "–"} % du chassé)</div>
      <div>Goulot : ${goulot ? `<span class="puce">${esc(goulot.m.pseudo)} · rang ${goulot.m.pos} · ${goulot.pct} % du chassé</span>` : "<b>aucun</b>"}</div>
      <div class="sous">Extérieur : +${fmt(x.extg)} / −${fmt(x.extp)} = <b>${sgn(x.extg - x.extp)}</b></div></div>`;
  }
  $("chaines").innerHTML = h;

  // 2. champions
  const champ = (typ, cle, meilleur) => {
    const c = stList.filter(s => s.m.type === typ && s[cle] !== null);
    return c.length ? c.reduce((a, b) => (meilleur ? b[cle] > a[cle] : b[cle] < a[cle]) ? b : a) : null;
  };
  const carteChamp = (titre, s, typ) => !s ? `<div class="carte"><h3>${titre}</h3><span class="vide">—</span></div>` :
    `<div class="carte"><h3>${titre}</h3><div class="chiffre">${esc(s.m.pseudo)}</div>
      <div class="sous">${esc(s.m.type)} · chaîne ${s.m.chaine} · rang ${s.m.pos}</div>
      <div>${typ === "Chasseur" ? `<b>${fmt(s.moy)}</b> chassés / jour${s.pct !== null ? ` (${s.pct} % du chassé de la chaîne)` : ""}`
        : `<b>${s.pct} %</b> du chassé de la chaîne (${fmt(s.moy)} envoyés / jour)`}</div></div>`;
  $("champions").innerHTML = carteChamp("🏆 Meilleur chasseur", champ("Chasseur", "moy", true), "Chasseur") +
    carteChamp("👾 Moins bon chasseur", champ("Chasseur", "moy", false), "Chasseur") +
    carteChamp("🏆 Meilleur passeur", champ("Passeur", "pct", true), "Passeur") +
    carteChamp("👾 Moins bon passeur", champ("Passeur", "pct", false), "Passeur");

  schema(W);

  // 3. origine du tdc
  const croissance = (arr.tdc !== null && dep.tdc !== null) ? arr.tdc - dep.tdc : null;
  const chasseAll = ch.ouest.chasse + ch.est.chasse;
  const ligne = (lib, x) => `<tr><td>${lib}</td><td>${fmt(x)}</td><td>${croissance ? (pct(x, croissance) ?? "") + " %" : ""}
    <span class="barreg" style="width:${Math.max(0, Math.min(100, pct(x, croissance) || 0)) * 1.2}px"></span></td></tr>`;
  $("origine").innerHTML = croissance === null ? `<p class="vide">Totaux d'alliance indisponibles sur cette plage.</p>` :
    `<table><tr><th>Origine du tdc gagné par l'alliance</th><th>tdc</th><th>% de la croissance</th></tr>` + ligne("Croissance du tdc total", croissance) +
    ligne("dont chasse (minimum)", chasseAll) + ligne("dont hors chasse (maximum = croissance − chasse)", Math.max(croissance - chasseAll, 0)) +
    `</table><p class="note">La part hors chasse est une fourchette : de la chasse masquée par une perte dans la même heure la réduit.</p>`;

  // 4. à signaler
  const flag = stList.filter(s => s.signaux.length).sort((a, b) => b.signaux.length - a.signaux.length || (a.pct ?? 999) - (b.pct ?? 999));
  $("signaler").innerHTML = flag.length ? `<table><tr><th>Joueur</th><th class="g">Rôle · chaîne</th><th class="g">Signaux</th></tr>` +
    flag.map(s => `<tr><td>${esc(s.m.pseudo)}</td><td class="g">${esc(rolePos(s.m))}</td><td class="g">${s.signaux.map(puce).join("")}</td></tr>`).join("") + "</table>"
    : `<p class="vide">Aucun signal sur la plage.</p>`;

  // 5. tous les joueurs
  const cl = c => c ? ` class="${c}"` : "";
  let t = `<table class="tj"><tr><th>Joueur</th><th>Moy. / jour</th><th>% du chassé</th><th class="opt">% hors chaîne</th><th>Tendance</th><th class="opt">% incertain</th><th>Pause max (h)</th><th class="g">Signaux</th></tr>`;
  for (const c of ["ouest", "est"]) {
    t += `<tr class="titre"><td colspan="8">Chaîne ${c}</td></tr>`;
    for (const typ of POSTES) for (const m of DATA.membres.filter(m => m.type === typ && m.chaine === c).sort((a, b) => a.pos - b.pos)) {
      const s = st[m.pseudo];
      const c2 = (typ !== "Chasseur" && s.pct !== null && s.pct < T.noeud) ? "rouge" : "";
      const fl = s.tendance ? `<span class="fl ${s.tendance === "↑" ? "vert" : s.tendance === "↓" ? "rouge" : ""}">${s.tendance}</span>` : "";
      const c6 = (s.inc !== null && s.inc > T.incertain) ? "jaune" : "", c7 = (s.hors !== null && s.hors > T.hors) ? "orange" : "";
      t += `<tr class="joueur" data-n="${esc(m.pseudo)}"><td><b>${esc(m.pseudo)}</b><div class="sous">${esc(m.type)} · ${m.pos}</div></td>
        <td>${fmt(s.moy)}</td><td${cl(c2)}>${s.pct !== null ? s.pct + " %" : ""}</td><td class="opt${c7 ? " " + c7 : ""}">${s.hors !== null ? s.hors + " %" : ""}</td><td>${fl}</td>
<td class="opt${c6 ? " " + c6 : ""}">${s.inc !== null ? s.inc + " %" : ""}</td>
        <td>${s.pause}</td><td class="g">${s.signaux.map(puce).join("")}</td></tr>`;
    }
  }
  $("joueurs").innerHTML = t + "</table>";
  document.querySelectorAll("tr.joueur").forEach(tr => tr.addEventListener("click", () => {
    const nxt = tr.nextElementSibling;
    if (nxt && nxt.classList.contains("detail")) { nxt.remove(); return; }
    const n = tr.dataset.n, set = new Set(W.idx), lances = {}, subis = {};
    for (const [i, a, c, x, conf] of DATA.att) if (set.has(i)) {
      if (a === n) { (lances[c] ||= {x: 0, q: false}).x += x; lances[c].q ||= conf === 1 || conf === 2; }
      if (c === n) { (subis[a] ||= {x: 0, q: false}).x += x; subis[a].q ||= conf === 1 || conf === 2; }
    }
    const liste = (o, f) => Object.entries(o).sort((a, b) => b[1].x - a[1].x).map(([k, v]) => `${f} ${esc(k)} ${fmt(v.x)}${v.q ? " ?" : ""}`).join(" ; ");
    const d = document.createElement("tr"); d.className = "detail";
    d.innerHTML = `<td colspan="8"><div><b>Envoyés</b> : ${liste(lances, "→") || "<span class=vide>aucun flood</span>"}</div>
      <div><b>Subis</b> : ${liste(subis, "←") || "<span class=vide>aucun</span>"}</div></td>`;
    tr.after(d);
  }));
  $("seuils").textContent = `Seuils : ralentit la chaîne < ${T.noeud} % du chassé ; perf en baisse < ${T.habitude} % des 48 h précédentes ; ` +
    `données fragiles > ${T.incertain} % d'envois à cible incertaine ; floods hors chaîne (vers un joueur hors alliance, plus de ${T.horsChasse} % du chassé quotidien de la chaîne) > ${T.hors} % ; ` +
    `Tout est comparé au tdc chassé de la chaîne. ` +
    `Tendance : la chasse (chasseurs) ou les floods envoyés (autres) sur la plage contre les 48 h qui la précèdent (↑ ↓ au-delà de ±${Math.round(T.tendance * 100)} %). « Pause max » : plus longue période sans activité. ` +
    `Jaune = données fragiles, orange = floods hors chaîne. « Aujourd'hui » et « Hier » suivent les jours à Paris.`;
}
$("plage").addEventListener("change", () => {
  $("perso").hidden = $("plage").value !== "perso";
  if ($("plage").value === "perso" && !$("debut").value) {
    const fin = S[S.length - 1].t; $("debut").value = jourParis(Math.max(S[0].t, fin - 3 * 24 * H)); $("fin").value = jourParis(fin);
    $("debut").min = $("fin").min = jourParis(S[0].t); $("debut").max = $("fin").max = jourParis(fin);
  }
  rendre();
});
$("debut").addEventListener("change", rendre); $("fin").addEventListener("change", rendre);
rendre();
</script>
</body>
</html>
"""
