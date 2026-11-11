/* Sas — portal logic. Plain ES modules-free script: no build step, no CDN.
 *
 * The page talks to the API of spec §23 with a bearer token. The tenant is
 * never a parameter (EF-51): it lives in the token. When the API is not
 * reachable, the page says so plainly instead of showing a fake dashboard —
 * an empty report presented as a result is exactly what this product refuses.
 */

const API = "";
let JETON = "";
let CAMPAGNE = "";
let LANGUE = "fr";

const $ = (id) => document.getElementById(id);

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

function etat(texte, classe = "") {
  const el = $("etat");
  el.textContent = texte;
  el.className = "etat " + classe;
}

function texte(el, valeur) {
  $(el).textContent = valeur;
}

async function amorcer() {
  try {
    const sante = await fetch(API + "/health").then((r) => r.json());
    JETON = sante.jeton_demo || "";
    etat("API en ligne", "ok");
  } catch (erreur) {
    etat("API injoignable — voir docs/TEST-INSTRUCTIONS.md", "ko");
  }
  await rafraichirRegistre();
}

async function rafraichirRegistre() {
  if (!JETON) return;
  try {
    const lignes = await appel("/registre");
    const corps = $("registre").querySelector("tbody");
    corps.innerHTML = "";
    if (!lignes.length) {
      corps.innerHTML = '<tr><td colspan="3" class="note">aucun agent homologué</td></tr>';
      return;
    }
    for (const agent of lignes) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${agent.nom}</td><td>${agent.version}</td><td>${agent.statut}</td>`;
      corps.appendChild(tr);
    }
  } catch (erreur) {
    console.error(erreur);
  }
}

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
    CAMPAGNE = resultat.id;
    afficher(resultat);
    await chargerRapport();
    await chargerAttestation();
    await rafraichirRegistre();
    etat("campagne terminée", "ok");
  } catch (erreur) {
    etat("échec : " + erreur.message, "ko");
    texte("verdict", "—");
  } finally {
    bouton.disabled = false;
  }
}

function afficher(r) {
  const verdict = $("verdict");
  verdict.textContent = r.verdict.toUpperCase();
  verdict.className = "verdict " + r.verdict;
  texte("sessions", r.sessions);
  texte("appels", r.appels);
  texte("refus", r.refus);
  texte("couverture", Number(r.couverture).toFixed(2));
  texte("compositions", r.compositions);
  texte("cout", Number(r.cout).toFixed(2));

  const corps = $("decouvertes").querySelector("tbody");
  corps.innerHTML = "";
  const libelles = {
    exploration: ["Exploration", "filtrée — bruit de raisonnement"],
    debordement: ["Débordement", "manifeste à compléter"],
    tentative: ["Tentative", "à investiguer"],
    hostile: ["Hostile", "refus d'homologation"],
    indeterminee: ["Indéterminée", "revue humaine"],
  };
  for (const [cle, compte] of Object.entries(r.decouvertes || {})) {
    const [nom, traite] = libelles[cle] || [cle, ""];
    const tr = document.createElement("tr");
    if (cle === "exploration") tr.className = "filtre";
    tr.innerHTML = `<td>${nom}</td><td>${compte}</td><td>${traite}</td>`;
    corps.appendChild(tr);
  }
  $("portee").textContent =
    "Voir l'attestation ci-dessous : la borne publiée dit ce que ces rejeux " +
    "prouvent, et ce qu'ils ne prouvent pas.";
}

async function chargerRapport() {
  if (!CAMPAGNE) return;
  try {
    const rapport = await appel(`/rapports/${CAMPAGNE}?langue=${LANGUE}`);
    $("rapport").textContent = rapport.texte;
    const ecarts = await appel(`/ecarts/${CAMPAGNE}`);
    const corps = $("ecarts").querySelector("tbody");
    corps.innerHTML = "";
    for (const ecart of ecarts) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${ecart.type}</td><td>${ecart.ressource}</td><td>${ecart.frequence}</td>`;
      corps.appendChild(tr);
    }
    const compositions = await appel("/compositions");
    const liste = $("compositions-liste");
    liste.innerHTML = "";
    if (!compositions.length) {
      liste.innerHTML = '<li class="note">aucune chaîne interdite détectée</li>';
    }
    for (const composition of compositions.slice(0, 8)) {
      const li = document.createElement("li");
      li.textContent = `${composition.motif} (${composition.nature})`;
      liste.appendChild(li);
    }
  } catch (erreur) {
    console.error(erreur);
  }
}

async function chargerAttestation() {
  if (!CAMPAGNE) return;
  try {
    const rapport = await appel(`/rapports/${CAMPAGNE}?langue=fr`);
    const bloc = rapport.texte.split("PORTÉE STATISTIQUE")[1] || "";
    $("attestation").textContent = ("PORTÉE STATISTIQUE" + bloc).slice(0, 1200);
  } catch (erreur) {
    console.error(erreur);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $("formulaire").addEventListener("submit", lancerCampagne);
  for (const bouton of document.querySelectorAll("button[data-langue]")) {
    bouton.addEventListener("click", () => {
      LANGUE = bouton.dataset.langue;
      for (const autre of document.querySelectorAll("button[data-langue]")) {
        autre.classList.toggle("actif", autre === bouton);
      }
      chargerRapport();
    });
  }
  amorcer();
});
