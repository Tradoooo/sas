/* Batterie de tests du portail Sas — Chromium headless (aucune fenêtre, aucun focus).
 *
 * Deux cibles :
 *   A. le site PUBLIC  https://baptistefaisy.github.io/sas/   (mode statique)
 *   B. le portail LOCAL http://127.0.0.1:<port>/               (mode direct, API réelle)
 *
 * Chaque vérification pousse une ligne {cible, nom, ok, detail}. Sortie : un
 * tableau + un compte, et une capture d'écran dans /tmp pour archive.
 */

// Playwright est résolu depuis NODE_PATH ou un node_modules voisin : le chemin
// n'est jamais codé en dur dans le dépôt.
//   NODE_PATH=/chemin/vers/node_modules node scripts/teste_portail.cjs
const { createRequire } = require("node:module");
const path = require("node:path");
let chromium;
const bases = [process.env.PLAYWRIGHT_BASE, process.cwd()].filter(Boolean);
const cibles = [];
for (const base of bases) {
  cibles.push(path.join(base, "node_modules", "playwright"));
  cibles.push(path.join(base, "node_modules", "playwright-core"));
  cibles.push("playwright");
  cibles.push("playwright-core");
}
for (const cible of cibles) {
  try {
    const module = require(cible);
    if (module && module.chromium) {
      chromium = module.chromium;
      break;
    }
  } catch (erreur) {
    /* on essaie le suivant */
  }
}
if (!chromium) {
  console.error("Playwright introuvable. Essayés : " + cibles.join(", "));
  console.error("Posez PLAYWRIGHT_BASE=/chemin/dun/projet/qui/linstall");
  process.exit(2);
}

const PUBLIC = process.env.SAS_PUBLIC_URL || "https://baptistefaisy.github.io/sas/";
const LOCAL = process.env.SAS_LOCAL_URL || "http://127.0.0.1:18123/";
const TEST_LOCAL = process.env.SAS_TEST_LOCAL === "1";

const resultats = [];
function verifier(cible, nom, ok, detail = "") {
  resultats.push({ cible, nom, ok: !!ok, detail: String(detail).slice(0, 220) });
}

/* Attendu : le LIBELLÉ i18n, jamais l'identifiant interne. Afficher
 * « HOMOLOGUE_SOUS_CONDITIONS » à un lecteur est un défaut, pas un style ;
 * les libellés viennent de sas.i18n via le jeu de données. */
const VERDICTS_ATTENDUS = {
  "demo-conforme": "Homologué",
  "demo-bavard": "Homologué sous conditions",
  "demo-curieux": "Refusé",
  "demo-opaque": "Non mesurable",
};

async function nouvellePage(navigateur) {
  const contexte = await navigateur.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await contexte.newPage();
  const erreurs = [];
  const requetes = [];
  page.on("console", (m) => {
    if (m.type() === "error") erreurs.push(m.text());
  });
  page.on("pageerror", (e) => erreurs.push(String(e)));
  page.on("request", (r) => requetes.push(r.url()));
  page._erreurs = erreurs;
  page._requetes = requetes;
  return page;
}

async function testerPublic(navigateur) {
  const page = await nouvellePage(navigateur);
  const cible = "PUBLIC";
  const reponse = await page.goto(PUBLIC, { waitUntil: "networkidle", timeout: 45000 });

  verifier(cible, "HTTP 200", reponse && reponse.status() === 200, reponse && reponse.status());
  verifier(cible, "titre de la page", (await page.title()).includes("Sas"), await page.title());

  // Le bandeau doit dire d'où viennent les chiffres.
  await page.waitForSelector("#mode-bandeau:not(.cache)", { timeout: 15000 }).catch(() => {});
  const bandeau = (await page.textContent("#mode-bandeau")) || "";
  verifier(cible, "bandeau = mode statique annoncé", /Mode statique/i.test(bandeau), bandeau.slice(0, 90));
  verifier(cible, "le bandeau cite la source des chiffres", /demo\.json|moteur/i.test(bandeau));
  verifier(cible, "avertissement « synthétiques » visible", await page.isVisible(".avertissement"));

  // Registre : 4 agents, cliquables.
  const lignes = await page.$$("#registre tbody tr");
  verifier(cible, "registre : 4 agents", lignes.length === 4, `${lignes.length} ligne(s)`);
  const noms = [];
  for (const ligne of lignes) noms.push(((await ligne.textContent()) || "").trim());
  verifier(cible, "registre : les 4 noms", noms.join("|").includes("demo-conforme") && noms.join("|").includes("demo-opaque"), noms.join(" | "));

  // Chaque agent, tour à tour.
  for (const nom of Object.keys(VERDICTS_ATTENDUS)) {
    await page.evaluate((n) => {
      const ligne = [...document.querySelectorAll("#registre tbody tr")].find((tr) => tr.textContent.includes(n));
      if (ligne) ligne.click();
    }, nom);
    await page.waitForTimeout(250);
    const verdict = ((await page.textContent("#verdict")) || "").trim();
    verifier(cible, `${nom} → verdict`, verdict === VERDICTS_ATTENDUS[nom], `attendu « ${VERDICTS_ATTENDUS[nom]} », lu « ${verdict} »`);

    const chiffres = await page.evaluate(() =>
      ["sessions", "appels", "refus", "couverture", "compositions", "cout"].map((id) => document.getElementById(id).textContent.trim())
    );
    verifier(cible, `${nom} → 6 indicateurs renseignés`, chiffres.every((c) => c && c !== "–"), chiffres.join("/"));

    const attestation = (await page.textContent("#attestation")) || "";
    if (nom === "demo-opaque") {
      verifier(cible, `${nom} → aucune attestation (ENF-17)`, /NON MESURABLE/i.test(attestation), attestation.slice(0, 70));
    } else {
      verifier(cible, `${nom} → portée statistique affichée`, /PORTÉE STATISTIQUE/.test(attestation), attestation.slice(0, 40));
      verifier(cible, `${nom} → « comportement rare » non exclu`, /rare/i.test(attestation));
    }
  }

  // Le curieux : compositions d'exfiltration visibles.
  await page.evaluate(() => {
    const ligne = [...document.querySelectorAll("#registre tbody tr")].find((tr) => tr.textContent.includes("demo-curieux"));
    if (ligne) ligne.click();
  });
  await page.waitForTimeout(250);
  const compositions = ((await page.textContent("#compositions-liste")) || "").toLowerCase();
  verifier(cible, "curieux → composition d'exfiltration affichée", compositions.includes("exfiltration"), compositions.slice(0, 70));

  // Le bavard : exploration filtrée et visible comme telle.
  await page.evaluate(() => {
    const ligne = [...document.querySelectorAll("#registre tbody tr")].find((tr) => tr.textContent.includes("demo-bavard"));
    if (ligne) ligne.click();
  });
  await page.waitForTimeout(250);
  const ligneExploration = await page.$("#decouvertes tbody tr.filtre");
  verifier(cible, "bavard → ligne Exploration marquée « filtrée »", !!ligneExploration);
  const ecarts = await page.$$("#ecarts tbody tr");
  verifier(cible, "bavard → écarts publiés", ecarts.length > 0, `${ecarts.length} ligne(s)`);

  // Bascule de langue.
  await page.click('button[data-langue="en"]');
  await page.waitForTimeout(300);
  const rapportEn = (await page.textContent("#rapport")) || "";
  verifier(cible, "bascule EN → rapport anglais", /HOMOLOGATION REPORT/.test(rapportEn), rapportEn.slice(0, 40));
  await page.click('button[data-langue="fr"]');
  await page.waitForTimeout(300);
  const rapportFr = (await page.textContent("#rapport")) || "";
  verifier(cible, "bascule FR → rapport français", /RAPPORT D'HOMOLOGATION/.test(rapportFr), rapportFr.slice(0, 40));
  verifier(cible, "le rapport liste ses limites (section 10)", /ne garantit pas/.test(rapportFr));

  // Le pied de page assume les limites.
  verifier(cible, "pied de page : « non mesurable »", /non mesurable/i.test(await page.textContent("footer")));
  verifier(cible, "pied de page : décision au commanditaire", /commanditaire/i.test(await page.textContent("footer")));

  // Cohérence page ↔ données publiées.
  const donnees = await page.evaluate(async () => {
    const r = await fetch("data/demo.json");
    return r.json();
  });

  // --- le replay du journal -------------------------------------------------
  await page.evaluate(() => {
    const ligne = [...document.querySelectorAll("#registre tbody tr")].find((tr) => tr.textContent.includes("demo-curieux"));
    if (ligne) ligne.click();
  });
  await page.waitForTimeout(400);
  const appels = await page.$$("#replay-journal .appel");
  verifier(cible, "replay : la session est rejouable appel par appel", appels.length > 0, `${appels.length} ligne(s)`);
  const refus = await page.$$("#replay-journal .appel.refuse");
  verifier(cible, "replay : les refus sont distingués des autorisations", refus.length > 0, `${refus.length} refus`);
  const courante = await page.$("#replay-journal .appel.courant");
  verifier(cible, "replay : une ligne est sélectionnée", !!courante);
  await page.click("#replay-suiv");
  await page.waitForTimeout(250);
  const position = (await page.textContent("#replay-position")) || "";
  verifier(cible, "replay : la position avance", /2 \/ /.test(position), position);

  // --- le graphe de la chaîne causale --------------------------------------
  const graphe = await page.$("#replay-graphe svg");
  verifier(cible, "graphe de la chaîne causale en SVG", !!graphe);
  const noeuds = await page.$$("#replay-graphe .noeud");
  verifier(cible, "graphe : un nœud par appel", noeuds.length > 0, `${noeuds.length} nœud(s)`);
  // Ce qui compte n'est pas la présence d'une URL — le graphe affiche des
  // destinations, ce sont des DONNÉES — mais le fait qu'il ne CHARGE rien :
  // pas de src/href distant, pas de script, pas d'import CSS.
  const htmlGraphe = await page.innerHTML("#replay-graphe");
  const chargeQuoiQueSoit = /(?:src|href)\s*=\s*["']https?:|<script|@import/i.test(htmlGraphe);
  verifier(cible, "graphe : rien n'est chargé de l'extérieur", !chargeQuoiQueSoit);

  // --- avant / après filtrage ----------------------------------------------
  const bruts = (await page.textContent("#filtrage-bruts")) || "";
  const restants = (await page.textContent("#filtrage-restent")) || "";
  verifier(cible, "avant/après : les deux volumes sont affichés", bruts.trim() !== "" && restants.trim() !== "", `${bruts} → ${restants}`);
  const explication = (await page.textContent("#filtrage-explication")) || "";
  verifier(cible, "avant/après : l'explication du filtrage est présente", explication.length > 40);

  // --- le mode juge --------------------------------------------------------
  const pageJuge = await page.context().newPage();
  await pageJuge.goto(PUBLIC + "?juge=1", { waitUntil: "networkidle" });
  await pageJuge.waitForTimeout(1200);
  const bandeauJuge = await pageJuge.$("#juge-bandeau:not(.cache)");
  verifier(cible, "mode juge : le bandeau s'affiche", !!bandeauJuge);
  const titre = (await pageJuge.textContent("#juge-titre")) || "";
  verifier(cible, "mode juge : la démo déroule sans clic", titre.length > 10, titre.slice(0, 60));
  await pageJuge.close();

  const lu = await page.evaluate(() =>
    [...document.querySelectorAll("#registre tbody tr")].map((tr) => tr.children[2].textContent.trim()).sort().join(",")
  );
  // Le registre affiche les libellés, le JSON porte les identifiants : on
  // compare donc les libellés attendus pour chaque identifiant du JSON.
  const libellesVerdict = donnees.libelles.fr.verdict;
  const attendusLibelles = donnees.agents.map((a) => libellesVerdict[a.resume.verdict]).sort().join(",");
  verifier(
    cible,
    "registre == data/demo.json (libellés)",
    lu === attendusLibelles,
    `page=${lu} json=${attendusLibelles}`
  );

  // Hygiène : aucune requête hors origine, aucune erreur console.
  // L'origine de référence est celle de la page réellement chargée, pas une URL
  // codée en dur : la même batterie tourne contre le site public et contre un
  // serveur local.
  const origine = new URL(page.url()).origin;
  const horsOrigine = page._requetes.filter((u) => !u.startsWith(origine));
  verifier(cible, "aucune requête ne quitte l'origine", horsOrigine.length === 0, horsOrigine.slice(0, 3).join(" "));
  verifier(cible, "aucune erreur console", page._erreurs.length === 0, page._erreurs.slice(0, 2).join(" | "));

  // Responsive : pas de débordement horizontal en 375 px.
  await page.setViewportSize({ width: 375, height: 800 });
  await page.waitForTimeout(300);
  const debordement = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  verifier(cible, "responsive 375 px sans débordement", debordement <= 1, `débordement ${debordement} px`);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.waitForTimeout(200);
  await page.screenshot({ path: "/tmp/sas-portail-public.png", fullPage: false });

  await page.context().close();
}

async function testerLocal(navigateur) {
  const cible = "LOCAL";
  const page = await nouvellePage(navigateur);
  let reponse;
  try {
    reponse = await page.goto(LOCAL, { waitUntil: "networkidle", timeout: 20000 });
  } catch (e) {
    verifier(cible, "le portail local répond", false, String(e).slice(0, 120));
    await page.context().close();
    return;
  }
  verifier(cible, "HTTP 200", reponse && reponse.status() === 200, reponse && reponse.status());

  await page.waitForSelector("#mode-bandeau:not(.cache)", { timeout: 15000 }).catch(() => {});
  const bandeau = (await page.textContent("#mode-bandeau")) || "";
  verifier(cible, "bandeau = mode direct", /Mode direct/i.test(bandeau), bandeau.slice(0, 80));

  // Lancement d'une campagne réelle depuis la page.
  await page.selectOption("#agent", "demo-curieux");
  await page.selectOption("#scenarios", ["S5", "S8"]);
  await page.fill("#rejeux", "2");
  await page.fill("#graine", "7");
  await page.click('#formulaire button[type="submit"]');
  await page.waitForFunction(() => {
    const v = document.getElementById("verdict").textContent.trim();
    return v && v !== "—" && !document.querySelector('#formulaire button[type="submit"]').disabled;
  }, { timeout: 90000 }).catch(() => {});
  // Le verdict affiché est le LIBELLÉ i18n (« Refusé »), jamais l'identifiant
  // interne (« refuse ») : c'est précisément ce que la page doit montrer.
  const verdict = ((await page.textContent("#verdict")) || "").trim();
  verifier(
    cible,
    "campagne lancée depuis la page → verdict en libellé",
    verdict === "Refusé",
    `lu « ${verdict} »`
  );
  verifier(cible, "le verdict n'est pas un identifiant brut", !/_/.test(verdict) && verdict === verdict.toUpperCase() === false, verdict);

  const couverture = (await page.textContent("#couverture")) || "";
  verifier(cible, "couverture du journal = 1.00 (KPI-4)", couverture.trim() === "1.00", couverture);
  const rapport = (await page.textContent("#rapport")) || "";
  verifier(cible, "rapport chargé en direct", /RAPPORT D'HOMOLOGATION/.test(rapport), rapport.slice(0, 40));

  // Les 22 routes de l'inventaire existent (401 sans jeton = la route existe).
  // La sonde volontairement non authentifiée provoque un 401 que le navigateur
  // journalise : on fige le compte des erreurs AVANT, pour ne pas compter comme
  // défaut de la page ce que le test a lui-même demandé.
  const erreursAvantSonde = page._erreurs.length;
  const statut = await page.evaluate(async () => {
    const r = await fetch("/health");
    return r.status;
  });
  verifier(cible, "/health répond", statut === 200, statut);
  const sansJeton = await page.evaluate(async () => (await fetch("/registre")).status);
  verifier(cible, "/registre sans jeton → 401 (EF-51)", sansJeton === 401, sansJeton);

  const nouvelles = page._erreurs.slice(erreursAvantSonde).filter((e) => !/401/.test(e));
  verifier(cible, "aucune erreur console (hors sonde volontaire)", nouvelles.length === 0, nouvelles.slice(0, 2).join(" | "));
  await page.screenshot({ path: "/tmp/sas-portail-local.png" });
  await page.context().close();
}

(async () => {
  const navigateur = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  try {
    await testerPublic(navigateur);
    if (TEST_LOCAL) await testerLocal(navigateur);
  } catch (e) {
    verifier("ERREUR", "exécution de la batterie", false, String(e));
  } finally {
    await navigateur.close();
  }

  const parCible = {};
  for (const r of resultats) {
    parCible[r.cible] = parCible[r.cible] || { ok: 0, ko: 0 };
    parCible[r.cible][r.ok ? "ok" : "ko"]++;
  }
  for (const r of resultats) {
    console.log(`${r.ok ? "✅" : "❌"} [${r.cible}] ${r.nom}${r.detail ? ` — ${r.detail}` : ""}`);
  }
  const ko = resultats.filter((r) => !r.ok);
  console.log(`\n${resultats.length} vérifications · ${resultats.length - ko.length} vertes · ${ko.length} rouge(s)`);
  for (const [cible, compte] of Object.entries(parCible)) console.log(`  ${cible}: ${compte.ok} vertes, ${compte.ko} rouges`);
  if (ko.length) {
    console.log("\nEN ÉCHEC :");
    for (const r of ko) console.log(`  - [${r.cible}] ${r.nom} : ${r.detail}`);
  }
  process.exit(ko.length ? 1 : 0);
})();
