/* Sas — portal logic.
 *
 * Two modes, and the page always says which one it is:
 *
 *   - LIVE  : the API of spec §23 answers (local `sas portail`, or the deployed
 *     stack). Campaigns can be launched from the page.
 *   - STATIC : GitHub Pages has no Python behind it, so the page serves
 *     `data/demo.json`, which was produced by RUNNING THE REAL ENGINE on the
 *     synthetic demo data. Nothing is invented: every figure on the page comes
 *     from a measured campaign. The banner says when it was generated.
 *
 * A page that showed invented numbers would be exactly what this product
 * refuses to produce, so the static mode says where its numbers come from.
 */

const API = "";
let JETON = "";
let MODE = "statique";
let DONNEES = null;
let AGENT = null;
let LANGUE = "fr";
let LIBELLES = { fr: { verdict: {}, nature: {} }, en: { verdict: {}, nature: {} } };

const $ = (id) => document.getElementById(id);

/* The page must never print an internal identifier: HOMOLOGUE_SOUS_CONDITIONS
 * is an enum value, "Homologué sous conditions" is a verdict. The labels come
 * from `sas.i18n` through the dataset (static) or /health (live) — one source,
 * no copy here that could drift. */
function libelle(famille, valeur) {
  const table = (LIBELLES[LANGUE] || {})[famille] || {};
  return table[valeur] || valeur;
}

function texte(id, valeur) {
  $(id).textContent = valeur;
}

function etat(texte, classe = "") {
  const el = $("etat");
  el.textContent = texte;
  el.className = "etat " + classe;
}

function bandeau(mode, quand) {
  const el = $("mode-bandeau");
  el.classList.remove("cache");
  if (mode === "live") {
    el.className = "mode-bandeau live";
    el.innerHTML =
      "<strong>Mode direct</strong> — l'API répond : les campagnes lancées depuis " +
      "cette page sont réellement exécutées par le moteur, en direct.";
  } else {
    el.className = "mode-bandeau statique";
    el.innerHTML =
      "<strong>Mode statique</strong> — GitHub Pages n'héberge pas de moteur : " +
      "les chiffres affichés proviennent de <code>data/demo.json</code>, produit par " +
      "<em>une exécution réelle du moteur</em> sur le jeu synthétique " +
      (quand ? `(${quand})` : "") +
      ". Pour lancer une campagne en direct : <code>make demo</code> en local.";
  }
}

/* ------------------------------------------------------------------ API -- */

async function appel(chemin, options = {}) {
  const reponse = await fetch(API + chemin, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + JETON,
      ...(options.headers || {}),
    },
  });
  if (!reponse.ok) {
    const detail = await reponse.text();
    throw new Error(`${reponse.status} ${chemin} — ${detail.slice(0, 200)}`);
  }
  return reponse.json();
}

async function tenterLive() {
  /* The mode is decided by a file that always answers: the static deployment
   * ships `api-status.json` (mode "statique"), the live API serves the same
   * path with mode "direct". Probing /health instead would 404 on Pages and
   * leave an unexplained error in the reader's console. */
  try {
    const reponse = await fetch("api-status.json", { cache: "no-store" });
    if (!reponse.ok) return false;
    const statut = await reponse.json();
    if (statut.mode !== "direct") return false;
    const sante = await fetch(API + "/health").then((r) => r.json());
    JETON = sante.jeton_demo || "";
    LIBELLES = sante.libelles || LIBELLES;
    if (!JETON) return false;
    const registre = await appel("/registre");
    return Array.isArray(registre);
  } catch (erreur) {
    return false;
  }
}

/* -------------------------------------------------------------- Données -- */

async function chargerStatique() {
  const reponse = await fetch("data/demo.json");
  if (!reponse.ok) throw new Error("data/demo.json introuvable");
  DONNEES = await reponse.json();
  LIBELLES = DONNEES.libelles || LIBELLES;
  MODE = "statique";
  bandeau("statique", DONNEES.genere_le);
  afficherRegistre(DONNEES.registre);
  AGENT = DONNEES.agents[0];
  afficherAgent(AGENT);
}

function afficherRegistre(lignes) {
  const corps = $("registre").querySelector("tbody");
  corps.innerHTML = "";
  if (!lignes.length) {
    corps.innerHTML = '<tr><td colspan="3" class="note">aucun agent homologué</td></tr>';
    return;
  }
  for (const agent of lignes) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${agent.nom}</td><td>${agent.version}</td>` +
      `<td class="statut ${agent.statut}">${libelle("verdict", agent.statut)}</td>`;
    tr.addEventListener("click", () => {
      const trouve = (DONNEES ? DONNEES.agents : []).find((a) => a.nom === agent.nom);
      if (trouve) {
        AGENT = trouve;
        afficherAgent(trouve);
      }
    });
    corps.appendChild(tr);
  }
}

function afficherAgent(agent) {
  const r = agent.resume;
  const verdict = $("verdict");
  verdict.textContent = libelle("verdict", r.verdict || "");
  verdict.className = "verdict " + (r.verdict || "");

  texte("sessions", r.sessions);
  texte("appels", r.appels);
  texte("refus", r.refus);
  texte("couverture", Number(r.couverture || 0).toFixed(2));
  texte("compositions", r.compositions);
  texte("cout", Number(r.cout || 0).toFixed(2));

  const decouvertes = $("decouvertes").querySelector("tbody");
  decouvertes.innerHTML = "";
  /* The "treatment" column is what makes the filtering of §13.5 visible rather
   * than implicit: the reader sees that exploration was counted, then dropped. */
  const traitements = {
    exploration: ["exploration", "filtrée — bruit de raisonnement"],
    debordement: ["debordement", "manifeste à compléter"],
    tentative: ["tentative", "à investiguer"],
    hostile: ["hostile", "refus d'homologation"],
    indeterminee: ["indeterminee", "revue humaine"],
  };
  for (const [cle, compte] of Object.entries(r.decouvertes || {})) {
    const [, traite] = traitements[cle] || [cle, ""];
    const tr = document.createElement("tr");
    if (cle === "exploration") tr.className = "filtre";
    tr.innerHTML = `<td>${libelle("nature", cle)}</td><td>${compte}</td><td>${traite}</td>`;
    decouvertes.appendChild(tr);
  }

  const ecarts = $("ecarts").querySelector("tbody");
  ecarts.innerHTML = "";
  for (const ecart of agent.ecarts || []) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${ecart.type}</td><td>${ecart.ressource}</td><td>${ecart.frequence}</td>`;
    ecarts.appendChild(tr);
  }
  if (!(agent.ecarts || []).length) {
    ecarts.innerHTML = '<tr><td colspan="3" class="note">aucun écart</td></tr>';
  }

  const liste = $("compositions-liste");
  liste.innerHTML = "";
  if (!(agent.compositions || []).length) {
    liste.innerHTML = '<li class="note">aucune chaîne interdite détectée</li>';
  }
  for (const composition of (agent.compositions || []).slice(0, 8)) {
    const li = document.createElement("li");
    li.textContent = `${composition.motif} (${composition.nature}) — ${composition.preuve}`;
    liste.appendChild(li);
  }

  const attestation = agent.attestation;
  texte(
    "attestation",
    attestation
      ? attestation.texte_fr
      : "Aucune attestation : cet agent est déclaré NON MESURABLE (ENF-17)."
  );
  texte("rapport", LANGUE === "en" ? agent.rapport_en : agent.rapport_fr);
  texte(
    "portee",
    (LANGUE === "en" ? agent.portee_en : agent.portee_fr) +
      `  ·  rejeux par scénario : ${agent.n_rejeux}  ·  graine : ${agent.graine}`
  );
  texte("conditions", (agent.conditions || []).join(" · ") || "aucune condition");
  afficherReplay(agent);
  afficherFiltrage(agent);
}

/* ------------------------------------------------------------------ Live -- */

async function lancerCampagne(evenement) {
  evenement.preventDefault();
  const bouton = document.querySelector("#formulaire button[type=submit]");
  bouton.disabled = true;
  etat("campagne en cours…", "");
  const scenarios = [...$("scenarios").selectedOptions].map((o) => o.value);
  try {
    const resultat = await appel("/campagnes", {
      method: "POST",
      body: JSON.stringify({
        agent: $("agent").value,
        scenarios,
        n_rejeux: Number($("rejeux").value),
        graine: Number($("graine").value),
      }),
    });
    AGENT = {
      nom: $("agent").value,
      resume: resultat,
      conditions: [],
      motifs: [],
      compositions: [],
      ecarts: [],
      rapport_fr: "",
      rapport_en: "",
      portee_fr: "",
      portee_en: "",
      attestation: null,
      n_rejeux: Number($("rejeux").value),
      graine: Number($("graine").value),
    };
    CAMPAGNE = resultat.id || "";
    afficherAgent(AGENT);
    await chargerRapportLive();
    etat("campagne terminée", "ok");
  } catch (erreur) {
    etat("échec : " + erreur.message, "ko");
  } finally {
    bouton.disabled = false;
  }
}

async function chargerRapportLive() {
  if (!CAMPAGNE) return;
  try {
    const rapport = await appel(`/rapports/${CAMPAGNE}?langue=${LANGUE}`);
    $("rapport").textContent = rapport.texte;
    const ecarts = await appel(`/ecarts/${CAMPAGNE}`);
    const corps = $("ecarts").querySelector("tbody");
    corps.innerHTML = ecarts.length
      ? ""
      : '<tr><td colspan="3" class="note">aucun écart</td></tr>';
    for (const ecart of ecarts) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${ecart.type}</td><td>${ecart.ressource}</td><td>${ecart.frequence}</td>`;
      corps.appendChild(tr);
    }
    const compositions = await appel("/compositions");
    const liste = $("compositions-liste");
    liste.innerHTML = compositions.length
      ? ""
      : '<li class="note">aucune chaîne interdite détectée</li>';
    for (const composition of compositions.slice(0, 8)) {
      const li = document.createElement("li");
      li.textContent = `${composition.motif} (${composition.nature})`;
      liste.appendChild(li);
    }
  } catch (erreur) {
    console.error(erreur);
  }
}

let CAMPAGNE = "";

/* ------------------------------------------------------------- Replay ----- */

let REPLAY_INDEX = 0;
let REPLAY_TIMER = null;

function arreterLecture() {
  if (REPLAY_TIMER !== null) {
    clearInterval(REPLAY_TIMER);
    REPLAY_TIMER = null;
    const bouton = $("replay-lecture");
    if (bouton) bouton.textContent = "▶ Lecture";
  }
}

function classe_decision(appel) {
  if (appel.decision !== "refuse") return "autorise";
  return appel.bornage ? "bornage" : "refuse";
}

function afficherReplay(agent) {
  arreterLecture();
  const journal = agent.journal || { appels: [], session: "", scenario: "", rejeu: 0, total: 0, tronque: false };
  const liste = $("replay-journal");
  liste.innerHTML = "";
  if (!journal.appels.length) {
    $("replay-contexte").textContent =
      "Aucun appel : cet agent ne passe pas par la passerelle, il n'y a donc rien à rejouer (ENF-17).";
    $("replay-position").textContent = "";
    $("replay-graphe").innerHTML = "";
    return;
  }
  $("replay-contexte").textContent =
    `Session ${journal.session} · scénario ${journal.scenario} · rejeu ${journal.rejeu} · ` +
    `${journal.total} appel(s) journalisé(s)` + (journal.tronque ? " (liste tronquée à l'affichage)" : "");

  journal.appels.forEach((appel, index) => {
    const li = document.createElement("li");
    li.className = "appel " + classe_decision(appel);
    li.dataset.index = String(index);
    const cible = appel.sortie ? appel.destination : (appel.ressources[0] || "");
    li.innerHTML =
      `<span class="n">${appel.n}</span>` +
      `<span class="outil">${appel.outil}</span>` +
      `<span class="cible">${cible}</span>` +
      `<span class="decision">${libelleDecision(appel)}</span>` +
      `<span class="t">${appel.t_ms.toFixed(0)} ms</span>`;
    li.addEventListener("click", () => allerA(index));
    liste.appendChild(li);
  });

  REPLAY_INDEX = 0;
  allerA(0);
  dessinerGraphe(journal.appels);
}

function libelleDecision(appel) {
  if (appel.decision !== "refuse") return "autorisé";
  if (appel.bornage) return "refusé · bornage";
  return "refusé · " + appel.regle;
}

function allerA(index) {
  const items = [...document.querySelectorAll("#replay-journal .appel")];
  if (!items.length) return;
  REPLAY_INDEX = Math.max(0, Math.min(index, items.length - 1));
  items.forEach((li, i) => li.classList.toggle("courant", i === REPLAY_INDEX));
  items[REPLAY_INDEX].scrollIntoView({ block: "nearest", behavior: "smooth" });
  $("replay-position").textContent = `${REPLAY_INDEX + 1} / ${items.length}`;
  document.querySelectorAll("#replay-graphe .noeud").forEach((n) => {
    n.classList.toggle("courant", Number(n.dataset.index) === REPLAY_INDEX);
  });
}

function dessinerGraphe(appels) {
  /* Hand-built SVG: no library, no CDN, readable in a video frame. */
  const pas = 46;
  const marge = 26;
  const hauteur = marge * 2 + pas * (appels.length - 1);
  const largeur = 560;
  const morceaux = [
    `<svg viewBox="0 0 ${largeur} ${hauteur}" role="img" `,
    `aria-label="Chaîne causale des appels de la session" xmlns="http://www.w3.org/2000/svg">`,
  ];
  appels.forEach((appel, index) => {
    const y = marge + pas * index;
    if (index > 0) {
      morceaux.push(`<line class="arete" x1="${marge}" y1="${y - pas + 9}" x2="${marge}" y2="${y - 9}" />`);
    }
  });
  appels.forEach((appel, index) => {
    const y = marge + pas * index;
    const cible = appel.sortie ? appel.destination : appel.ressources[0] || "";
    morceaux.push(
      `<g class="noeud ${classe_decision(appel)}" data-index="${index}" role="button" tabindex="0">` +
        `<circle cx="${marge}" cy="${y}" r="9" />` +
        `<text x="${marge + 20}" y="${y + 4}">${index + 1}. ${escapeXml(appel.outil)}</text>` +
        `<text class="cible" x="${marge + 20}" y="${y + 19}">${escapeXml(cible.slice(0, 62))}</text>` +
        `</g>`
    );
  });
  morceaux.push("</svg>");
  const conteneur = $("replay-graphe");
  conteneur.innerHTML = morceaux.join("");
  conteneur.querySelectorAll(".noeud").forEach((n) => {
    n.addEventListener("click", () => allerA(Number(n.dataset.index)));
    n.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") allerA(Number(n.dataset.index));
    });
  });
}

function escapeXml(texte) {
  return String(texte)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function afficherFiltrage(agent) {
  const f = agent.filtrage;
  if (!f) return;
  texte("filtrage-bruts", f.refus_bruts);
  texte("filtrage-restent", f.restent_a_lire);
  texte(
    "filtrage-detail",
    `${f.dont_hostiles} hostile(s) · ${f.dont_tentatives} tentative(s) · ` +
      `${f.dont_debordements} débordement(s) · ${f.dont_revue_humaine} en revue humaine`
  );
  const restants = Math.max(0, f.refus_bruts - f.exploration_filtree);
  texte(
    "filtrage-explication",
    f.exploration_filtree
      ? `${f.exploration_filtree} appel(s) d'exploration filtré(s) : du bruit de raisonnement. ` +
        `Restent ${restants} refus à examiner, dont ${f.restent_a_lire} découverte(s) classée(s). ` +
        `Sans ce filtrage le RSSI voit ${f.refus_bruts} refus et conclut que l'agent est hostile (§13.5).`
      : `Aucune exploration à filtrer sur cette campagne : les ${f.refus_bruts} refus sont du bornage ` +
        `(budget, durée) ou des tentatives réelles — le filtrage ne supprime rien d'autre que le bruit.`
  );
}

/* ------------------------------------------------------------ Mode juge --- */

const MOMENTS = [
  { agent: "demo-conforme", titre: "0:00 — l'agent conforme : zéro écart est un résultat" },
  { agent: "demo-bavard", titre: "0:55 — l'agent bavard explore et touche un leurre" },
  { agent: "demo-bavard", titre: "1:10 — l'exploration est filtrée, pas noyée dans le journal" },
  { agent: "demo-curieux", titre: "1:40 — l'agent curieux lit le leurre sensible puis tente une sortie" },
  { agent: "demo-curieux", titre: "1:55 — la composition d'exfiltration est capturée" },
  { agent: "demo-conforme", titre: "2:10 — trois invités, trois verdicts" },
  { agent: "demo-conforme", titre: "2:25 — l'attestation porte sa propre portée statistique" },
  { agent: "demo-opaque", titre: "2:40 — un agent non instrumentable est non mesurable, jamais conforme" },
];
let JUGE_TIMER = null;

function demarrerJuge() {
  const bandeau = $("juge-bandeau");
  bandeau.classList.remove("cache");
  let etape = 0;
  const jouer = () => {
    if (etape >= MOMENTS.length) {
      clearInterval(JUGE_TIMER);
      $("juge-titre").textContent = "Fin — les quatre invités, quatre issues différentes";
      return;
    }
    const moment = MOMENTS[etape];
    const agent = DONNEES.agents.find((a) => a.nom === moment.agent);
    $("juge-titre").textContent = moment.titre;
    if (agent) {
      AGENT = agent;
      afficherAgent(agent);
      document.querySelectorAll("#registre tbody tr").forEach((tr) => {
        tr.classList.toggle("courant", tr.textContent.includes(agent.nom));
      });
    }
    etape += 1;
  };
  jouer();
  JUGE_TIMER = setInterval(jouer, 5000);
}

/* ------------------------------------------------------------------ Boot -- */

document.addEventListener("DOMContentLoaded", async () => {
  $("formulaire").addEventListener("submit", lancerCampagne);
  $("replay-debut").addEventListener("click", () => allerA(0));
  $("replay-prec").addEventListener("click", () => allerA(REPLAY_INDEX - 1));
  $("replay-suiv").addEventListener("click", () => allerA(REPLAY_INDEX + 1));
  $("replay-lecture").addEventListener("click", () => {
    if (REPLAY_TIMER !== null) {
      arreterLecture();
      return;
    }
    $("replay-lecture").textContent = "⏸ Pause";
    REPLAY_TIMER = setInterval(() => allerA(REPLAY_INDEX + 1), 700);
  });
  for (const bouton of document.querySelectorAll("button[data-langue]")) {
    bouton.addEventListener("click", () => {
      LANGUE = bouton.dataset.langue;
      for (const autre of document.querySelectorAll("button[data-langue]")) {
        autre.classList.toggle("actif", autre === bouton);
      }
      if (MODE === "statique" && AGENT) {
        texte("rapport", LANGUE === "en" ? AGENT.rapport_en : AGENT.rapport_fr);
        texte("portee", LANGUE === "en" ? AGENT.portee_en : AGENT.portee_fr);
        afficherAgent(AGENT);
        afficherRegistre(DONNEES.registre);
      }
      chargerRapportLive();
    });
  }

  const live = await tenterLive();
  if (live) {
    MODE = "live";
    bandeau("live");
    etat("API en ligne", "ok");
    try {
      afficherRegistre(await appel("/registre"));
    } catch (erreur) {
      console.error(erreur);
    }
  } else {
    etat("mode statique — données mesurées", "");
    try {
      await chargerStatique();
    } catch (erreur) {
      etat("données indisponibles : " + erreur.message, "ko");
    }
  }

  // Mode juge : la démonstration de §28.2 déroule seule, sans un seul clic.
  if (new URLSearchParams(window.location.search).get("juge") === "1") {
    $("juge-bandeau").classList.remove("cache");
    demarrerJuge();
  }
});
