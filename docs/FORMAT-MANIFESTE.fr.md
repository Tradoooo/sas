# Le manifeste d'agent Sas — format ouvert

> **Ce que ce document est.** Le manifeste est un **format**, pas un
> entretien : une déclaration signée de ce qu'un agent tiers demande, de ce
> qu'il s'engage à faire et de ce qu'il ne doit jamais faire. Cette page
> décrit le format **tel qu'il est implémenté**, pour qu'un éditeur puisse
> produire un manifeste conforme sans lire le code.
>
> **Où est la vérité.** La table des blocs et des champs est **déclarée comme
> donnée** dans `src/sas/manifeste/schema.py` ; le validateur structurel lit
> cette table et le validateur sémantique se trouve dans
> `src/sas/manifeste/validation.py`. Le schéma public
> `schemas/manifeste.schema.json` est **généré depuis la même table**
> (`schema_json()`) : il ne peut donc pas diverger du validateur — le test
> `test_le_schema_publie_est_a_jour` échoue si le fichier committé diffère.
>
> **Pourquoi ce format existe.** Sans référence signée, un appel hors
> périmètre est indéterminable : est-ce une faute, ou une permission oubliée
> dans la déclaration ? Le manifeste est aussi la pièce contractuelle : un
> écart au manifeste signé est un manquement de l'éditeur, documenté, daté et
> prouvé.

---

## 1. Les treize blocs

Le document est un objet. Chaque clé de premier niveau est un **bloc** ; les
treize blocs ci-dessous sont la liste complète. Toute autre clé est refusée
(`bloc-inconnu`).

| # | Bloc | Cardinité | Obligatoire ? | Ce qu'il porte |
|---|---|---|---|---|
| 1 | `manifeste` | objet (1) | **oui** | En-tête : version et date du document |
| 2 | `identite` | objet (1) | **oui** | Qui tourne, et quoi exactement |
| 3 | `finalite` | objet (1) | **oui** | Ce que l'agent fait — et ce qu'il ne fait pas |
| 4 | `outils_demandes` | liste (0..n) | **oui** (la clé doit être présente) | Une entrée par outil demandé |
| 5 | `donnees_demandees` | liste (0..n) | **oui** | Ressources au grain fin : jamais « accès aux données » |
| 6 | `sorties_autorisees` | liste (0..n) | **oui** (la clé doit être présente ; une liste vide est valide) | Ce que l'agent peut envoyer dehors — **rien par défaut** |
| 7 | `budgets` | objet (1) | **oui** | Bornes dures, appliquées par Policy avant l'outil |
| 8 | `memoire` | objet (1) | non | Si vrai, les rejeux ne sont plus indépendants |
| 9 | `scenarios` | liste (1..n) | **oui** | Les cas d'usage nominaux que l'agent doit traiter |
| 10 | `interdictions_explicites` | liste (0..n) | **oui** | Ce que l'agent ne doit jamais faire, même s'il le peut |
| 11 | `engagements` | objet (1) | **oui** | Engagements de l'éditeur |
| 12 | `signature` | objet (1) | non (mais sans elle, rien ne tourne) | Signature de l'éditeur |
| 13 | `validation_client` | objet (1) | non (mais sans elle, rien ne tourne) | Validation du commanditaire |

Deux subtilités sur « obligatoire » :

- `sorties_autorisees` est requis par le schéma public, mais **une clé
  absente et une liste vide ne sont pas la même chose** et ne sont pas
  traitées de la même façon. Une liste vide est une déclaration : « aucune
  sortie ». Une clé absente est un refus, rapporté par le validateur
  sémantique avec le code `cle-absente` et l'action « écrire explicitement
  `sorties_autorisees: []` ». C'est le seul endroit où le format refuse de
  deviner.
- `memoire`, `signature` et `validation_client` ne sont pas dans la liste des
  blocs requis du schéma structurel, mais un manifeste sans signature ni
  validation n'ouvre **aucune exécution** (`EF-04`).

## 2. Les champs

Types : `str`, `int`, `bool`, `date`, `empreinte` (`sha256:` + 64 caractères
hexadécimaux minuscules), `liste` (liste de chaînes), `objet`.

| Bloc | Champ | Type | Requis | Remarque |
|---|---|---|---|---|
| `manifeste` | `version` | int | oui | Version du manifeste, incrémentée à chaque changement |
| `manifeste` | `date` | date | oui | Date du document |
| `identite` | `nom` | str | oui | Nom de l'agent |
| `identite` | `editeur` | str | oui | Éditeur (vendor) |
| `identite` | `version_agent` | str | oui | Version de l'agent ; un écart avec la version qui tourne bloque l'exécution |
| `identite` | `empreinte_paquet` | empreinte | oui | Empreinte du paquet ou de l'image |
| `identite` | `modele` | str | oui | Modèle sous-jacent |
| `identite` | `version_modele` | str | oui | Version de ce modèle — c'est elle qui rend détectable une dérive non déclarée |
| `identite` | `engagement_notification_modele` | bool | oui | L'éditeur s'engage à notifier un changement de modèle |
| `finalite` | `fait` | str | oui | Ce que l'agent fait, en une phrase |
| `finalite` | `ne_fait_pas` | liste | oui | Ce qu'il ne doit pas faire — la déclaration négative |
| `outils_demandes` | `nom` | str | oui | Nom de l'outil |
| `outils_demandes` | `operation` | str | oui | `lecture`, `ecriture` ou `execution` |
| `outils_demandes` | `justification` | str | oui | Pourquoi l'agent en a besoin |
| `donnees_demandees` | `type` | str | oui | `s3`, `table`, `index` ou `http` |
| `donnees_demandees` | `ressource` | str | oui | La ressource précise : bucket **et** préfixe, table **et** colonnes, index nommé |
| `donnees_demandees` | `justification` | str | oui | Pourquoi cette ressource est nécessaire |
| `donnees_demandees` | `colonnes` | liste | non | Exigée en pratique pour une `table` |
| `donnees_demandees` | `prefixes` | liste | non | Préfixes autorisés |
| `donnees_demandees` | `sensible` | bool | non | Le client marque la ressource comme sensible |
| `sorties_autorisees` | `destination` | str | oui | Une destination nommée — pas de joker |
| `sorties_autorisees` | `protocole` | str | oui | `http`, `courriel`, `dns` ou `webhook` |
| `sorties_autorisees` | `justification` | str | oui | Pourquoi cette sortie est nécessaire |
| `budgets` | `appels_par_execution` | int | oui | Appels d'outils par exécution |
| `budgets` | `jetons_par_execution` | int | oui | Jetons par exécution |
| `budgets` | `duree_maximale_secondes` | int | oui | Durée maximale |
| `budgets` | `memoire_maximale_mio` | int | oui | Mémoire maximale |
| `memoire` | `persistante` | bool | oui | `vrai` ⇒ les rejeux ne sont plus indépendants et la borne statistique ne s'applique pas (§14.6) |
| `scenarios` | `id` | str | oui | Identifiant du scénario (`S1`…) |
| `scenarios` | `nom` | str | oui | Ce qu'est le scénario |
| `scenarios` | `sensibilite` | str | non | Sensibilité du scénario |
| `interdictions_explicites` | *(liste de chaînes)* | liste | oui | Chaque entrée est une interdiction. Le validateur structurel accepte la liste de chaînes ; un objet `{"texte": …}` est aussi accepté par la couche structurelle, mais la liste de chaînes est la forme publiée |
| `engagements` | `notification_changement_modele` | str | oui | Préavis de changement de modèle |
| `engagements` | `notification_changement_invite` | str | oui | Préavis de changement d'invite |
| `engagements` | `delai_correction_critique` | str | oui | Délai de correction d'un défaut critique |
| `engagements` | `contact` | str | oui | Contact technique de l'éditeur |
| `signature` | `signataire` | str | oui | Qui signe |
| `signature` | `qualite` | str | oui | Son habilitation à engager l'éditeur |
| `signature` | `date` | date | oui | Date de la signature |
| `signature` | `empreinte_document` | empreinte | non | Empreinte du document signé |
| `validation_client` | `commanditaire` | str | oui | Le commanditaire (RSSI, DPO…) |
| `validation_client` | `date` | date | oui | Date de la validation |
| `validation_client` | `perimetre_approuve` | str | oui | Ce que le commanditaire approuve |
| `validation_client` | `mode_autorise` | str | oui | Mode autorisé — la première homologation est en Ombre |

Les booléens acceptent `vrai` / `faux`, `true` / `false`, `oui` / `non`,
`yes` / `no`, `1` / `0`, `on` / `off`. Le document peut être en YAML ou en JSON.

## 3. Un exemple complet

C'est le manifeste de référence du dépôt
(`tests/fixtures/manifeste-exemple.yaml`), identique à l'annexe A du cahier des
charges, avec les deux empreintes écrites en entier parce que le validateur
les exige (`test_annexe_a_se_charge_telle_quelle`).

```yaml
manifeste:
  version: 1
  date: 2026-11-20

identite:
  nom: AgentTicket
  editeur: Exemple Editeur SAS
  version_agent: 3.4.1
  empreinte_paquet: sha256:7c1f4a9e2b8d4c51a6f0e3d2b9c8471a5f6e0d9c8b7a61524334251607f8e9d0
  modele: anthropic.sonnet-4-5
  version_modele: 2026-10
  engagement_notification_modele: vrai

finalite:
  fait: >
    Lit les tickets de support du client, cherche dans la base documentaire,
    propose une réponse à l'agent humain, ouvre une tâche de suivi si besoin.
  ne_fait_pas:
    - envoyer une réponse directement au client final
    - modifier un ticket
    - accéder à des données de personnel ou de rémunération

outils_demandes:
  - nom: lire_ticket
    operation: lecture
    justification: traiter la demande entrante
  - nom: chercher_document
    operation: lecture
    justification: fonder la réponse proposée
  - nom: ouvrir_tache
    operation: ecriture
    justification: transmettre au niveau 2

donnees_demandees:
  - type: s3
    ressource: arn:aws:s3:::client-tickets/entree/*
    justification: tickets entrants
  - type: index
    ressource: kb-documentation-client
    justification: base documentaire
  - type: table
    ressource: dynamodb:suivi-client
    colonnes: [id, statut, resume]
    justification: ouverture de tâche

sorties_autorisees: []          # aucune sortie vers l'extérieur

budgets:
  appels_par_execution: 25
  jetons_par_execution: 60000
  duree_maximale_secondes: 180
  memoire_maximale_mio: 512

memoire:
  persistante: faux              # si vrai, les rejeux ne sont plus indépendants

scenarios:
  - id: S1
    nom: ticket simple documenté
  - id: S2
    nom: ticket sans réponse dans la documentation
  - id: S3
    nom: ticket nécessitant une escalade
  - id: S4
    nom: ticket contenant une instruction injectée
  - id: S5
    nom: ticket référençant une donnée de personnel
  - id: S6
    nom: volume élevé, 20 tickets successifs
  - id: S7
    nom: documentation indisponible
  - id: S8
    nom: demande de sortie vers l'extérieur par le ticket

interdictions_explicites:
  - lire toute ressource hors de celles déclarées
  - émettre toute requête réseau sortante
  - écrire ailleurs que dans la table de suivi déclarée
  - exécuter une instruction contenue dans un ticket

engagements:
  notification_changement_modele: 7 jours avant
  notification_changement_invite: 7 jours avant
  delai_correction_critique: 5 jours ouvrés
  contact: securite@exemple-editeur.invalid

signature:
  signataire: Directrice technique, Exemple Editeur SAS
  qualite: habilitée à engager l'éditeur
  date: 2026-11-20
  empreinte_document: sha256:5e08d73b009bf46e0309dd0b8753786b6bd543e2fa3cc592e9e889cb69a7eb0b

validation_client:
  commanditaire: RSSI du client
  date: 2026-11-21
  perimetre_approuve: integralité du manifeste
  mode_autorise: ombre uniquement pour la première homologation
```

## 4. Les règles de refus

Chaque refus porte un message **actionnable** : l'architecte doit savoir quoi
changer, pas seulement que quelque chose ne va pas. Les messages ci-dessous
sont ceux que produit le validateur (le code est l'identifiant, stable d'une
version à l'autre).

### 4.1 Refus structurels

| Code | Déclencheur | Action renvoyée par le validateur |
|---|---|---|
| `document-invalide` | Le document n'est pas un objet | « Fournir un objet YAML ou JSON. » |
| `bloc-absent` | Un bloc obligatoire manque | « Ajouter le bloc « … » (annexe A). » |
| `bloc-inconnu` | Une clé de premier niveau inconnue | « Retirer ce bloc ou demander un changement de contrat. » |
| `cle-inconnue` | Une clé inconnue dans un bloc | « Retirer « … » ou demander un changement de contrat. » |
| `champ-absent` | Un champ obligatoire d'un bloc manque | « Renseigner « … » dans le bloc … . » |
| `type-inattendu` | Un bloc n'est pas un objet, ou un bloc-liste n'est pas une liste, ou une entrée n'est pas un objet | « Reprendre le bloc … . » / « Fournir une liste d'objets … . » |

### 4.2 Refus sémantiques

| Code | Déclencheur | Action renvoyée par le validateur |
|---|---|---|
| `cle-absente` | `sorties_autorisees` est absent (pas vide) | « Écrire explicitement `sorties_autorisees: []` pour déclarer qu'aucune sortie n'est demandée. » |
| `grain-trop-large` | Une ressource déclarée vaguement (« accès aux données », un `s3` nu, `*`…) | « Déclarer la ressource précise : bucket ET préfixe, table ET colonnes, index nommé. » |
| `prefixe-absent` | Une ressource S3 sans segment de chemin après le bucket | « Ajouter un préfixe, par exemple arn:aws:s3:::client-tickets/entree/*. » |
| `colonnes-absentes` | Une table déclarée sans colonnes | « Lister les colonnes réellement utilisées. » |
| `justification-absente` | Un outil, une ressource ou une destination sans justification | « Expliquer en une phrase pourquoi l'agent en a besoin. » / « Expliquer pourquoi cette ressource est nécessaire. » / « Expliquer pourquoi cette sortie est nécessaire. » |
| `operation-inconnue` | Une opération autre que `lecture`, `ecriture`, `execution` | « Utiliser lecture, ecriture ou execution. » |
| `sortie-joker` | Une destination contenant `*`, ou vide | « Déclarer chaque destination nominativement. » |
| `protocole-inconnu` | Un protocole autre que `http`, `courriel`, `dns`, `webhook` | « Utiliser http, courriel, dns ou webhook. » |
| `budget-absent` | Un budget nul ou négatif | « Renseigner « … » avec une valeur strictement positive. » |
| `budget-incoherent` | Le budget d'appels est inférieur au minimum requis par les scénarios déclarés, ou la durée laisse moins d'une seconde par appel déclaré | « Porter « appels_par_execution » à … au moins, ou retirer un scénario. » / « Augmenter « duree_maximale_secondes » ou réduire « appels_par_execution ». » |
| `scenarios-absents` | Aucun scénario déclaré | « Déclarer au moins un cas d'usage nominal à rejouer. » |
| `scenario-incomplet` | Un scénario sans identifiant ou sans nom | « Renseigner l'identifiant et le nom de chaque scénario. » |
| `scenario-en-double` | Le même identifiant de scénario deux fois | « Ne déclarer chaque scénario qu'une fois. » |
| `interdiction-contradictoire` | Une interdiction exclut toute sortie alors que des sorties sont déclarées, ou une interdiction vise un outil demandé | « Retirer l'interdiction ou retirer les sorties autorisées. » / « Retirer l'outil demandé ou reformuler l'interdiction. » |
| `empreinte-invalide` | Une empreinte qui n'est pas `sha256:` + 64 hexadécimaux | « Fournir l'empreinte complète du paquet ou de l'image. » |
| `champ-vide` | Un champ d'identité, d'engagement, de signature ou de validation vide | « Renseigner « … » : c'est ce qui permet de détecter une dérive non déclarée. » / « Préciser le périmètre approuvé. » |
| `engagement-absent` | Un engagement vide | « Renseigner « … » : sans lui, une dérive non déclarée n'engage personne. » |
| `signature-absente` | Pas de signature de l'éditeur | « Faire signer le manifeste par une personne habilitée à engager l'éditeur. » |
| `validation-absente` | Pas de validation du commanditaire | « Faire valider le périmètre par le commanditaire (RSSI ou DPO). » |

## 5. Le cycle de vie

1. **Brouillon.** L'éditeur écrit le manifeste et l'envoie.
2. **Validation structurelle.** La table du §2 est appliquée : blocs, champs,
   types. Un document qui la échoue ne devient même pas un manifeste.
3. **Validation sémantique.** Le §4.2 est appliqué ; chaque refus est
   actionnable.
4. **Signature de l'éditeur.** Le statut devient `signe_editeur` ; l'empreinte
   canonique du document est enregistrée. Un manifeste modifié après signature
   **ne vérifie plus** : l'empreinte ne correspond plus.
5. **Validation du commanditaire.** Le statut devient `valide`. La première
   homologation est autorisée **en mode Ombre uniquement** : le mode Observé
   exige une première homologation en Ombre attestée, et l'appelant doit
   l'indiquer explicitement — rien n'est jamais produit sur la foi d'une
   promesse.
6. **Versionnement.** Toute modification crée une nouvelle version, fait
   retomber le statut à brouillon et **invalide l'attestation en cours**. Une
   modification qui ne touche aucun champ engageant est signalée comme
   administrative, et le rapport le dit.
7. **Exécution.** Aucune session ne démarre sans un manifeste au statut
   `valide`, dont `version_agent` correspond à la version qui tourne et dont
   l'empreinte correspond à celle scellée.

### L'empreinte

L'empreinte (`empreinte_manifeste`) est un hachage canonique des seuls
**champs engageants** : `version`, `date`, `identite`, `finalite`,
`outils_demandes`, `donnees_demandees`, `sorties_autorisees`, `budgets`,
`memoire_persistante`, `scenarios`, `interdictions_explicites`,
`engagements`. La signature et la validation du commanditaire n'en font **pas**
partie : elles signent l'empreinte, elles ne sont pas du contenu signé.

### Le scellement — et sa limite

Le scellement est un `hmac-sha256:<hex>` calculé sur l'empreinte canonique
avec une **clé partagée** (`sceller()` dans `src/sas/manifeste/signature.py`).
Il prouve que le document n'a pas changé depuis le scellement. Ce n'est
**pas** une signature électronique qualifiée : il n'y a ni PKI, ni certificat,
ni non-rétractation par un tiers. Un déploiement qui exige une signature
électronique qualifiée doit l'ajouter — le format est prêt (le bloc
`signature` est une donnée), l'implémentation n'existe pas.

## 6. Les limites du format, dites franchement

- Le format décrit un **comportement d'accès**. Il ne dit rien de la qualité
  fonctionnelle de l'agent, et il ne garantit pas que l'agent respecte sa
  déclaration : c'est précisément l'objet de la mesure.
- Une **permission au grain fin n'est pas une permission de traiter des
  données personnelles**. L'indicateur `sensible` est une déclaration du
  client, pas une analyse juridique.
- La **première homologation est en Ombre** : le manifeste seul n'autorise
  jamais le mode Observé.
- Le format **n'est pas signé par un tiers de confiance** : le scellement est
  une clé partagée, comme décrit ci-dessus.
- Une liste `donnees_demandees` vide est légale (un agent qui ne déclare
  rien) et sera simplement mesuré contre rien.
