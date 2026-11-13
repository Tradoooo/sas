# Sas — le guide du jury (3 minutes)

> Ce document est écrit pour quelqu'un qui a deux minutes et un scepticisme
> légitime. Chaque affirmation ci-dessous pointe vers **un artefact vérifiable**,
> pas vers une promesse. Ce qui n'est pas fait est dit comme tel, à la même
> place que ce qui l'est.

## 1. En une phrase

Sas est un ** sas à airtight** pour agents IA tiers : un agent d'éditeur n'entre
pas chez le client, il passe d'abord par une **homologation** (scénarios typés,
identité éphémère, périmètre déclaré, budgets bornés, journal complet de chaque
appel d'outil) et il n'en sort qu'avec une **attestation** datée qui dit ce
qu'il fait — et ce que N rejeux ne prouvent **pas**.

## 2. Montrez-moi, tout de suite, sans compte

| Ce que je veux voir | Où |
|---|---|
| La démo, publique, sans installation | <https://tradoooo.github.io/sas/> |
| Le dépôt, avec l'historique et les tests | <https://github.com/Tradoooo/sas> |
| La démo jouée en local | `make install && make demo` |

La page est servie en **mode statique** : GitHub Pages n'a pas de Python
derrière elle, donc les chiffres viennent de `portal/data/demo.json`, produit
par **le vrai moteur**. Le job de déploiement **régénère ce fichier et le
compare octet pour octet** à chaque push sur `main` — une page publique périmée
fait échouer la construction. C'est vérifiable : la preuve est dans
`.github/workflows/deploy.yml`.

## 3. Montrez-moi que ce n'est pas une maquette

| Question | Preuve |
|---|---|
| Le moteur est-il exécuté, pas simulé ? | 592 tests hors ligne + 11 tests **contre le vrai stack AWS déployé** (`tests/unit/aws/test_store_reel.py`, marqueur `aws`) |
| La pile est-elle réellement déployée ? | `cdk deploy sas-donnees-dev` : 16 tables DynamoDB + le seau de preuves, dans `eu-west-3` |
| L'écriture tient-elle dans le temps ? | La démo tourne contre les vraies tables : `python3 -m sas.cli demo --store dynamodb --tenant tenant-demo` |
| Le journal est-il croyable ? | Chaîne par empreintes, vérifiée à la relecture depuis DynamoDB ; rupture détectée à la lecture |
| Les chiffres sont-ils reproductibles ? | Horloge figée : deux générations du jeu de données donnent les mêmes octets (ENF-11) |
| Les limites sont-elles écrites ? | `docs/LIMITES.md`, `docs/ECHECS.md` (dix échecs assumés), et ces limites sont **imprimées sur l'attestation** elle-même |

## 4. Dites-moi ce que ça ne fait pas

C'est la partie qui rend le reste crédible. La liste complète et à jour est
`docs/ECHECS.md` ; en résumé :

- le mode Ombre ne révèle pas les comportements qui **dépendent des données
  réelles** (§10.4) — c'est pourquoi le mode Observé existe ;
- les canaux cachés fins ne sont pas détectés, et les six canaux non couverts
  sont **nommés** (`docs/CANAUX-CACHES.md`) ;
- une homologation sur N rejeux ne prouve **rien** au-delà de la borne
  publiée, et cette borne est imprimée sur chaque attestation ;
- la signature est un sceau HMAC (pas une signature KMS) : elle prouve
  l'intégrité à qui détient la clé, pas l'opposabilité à un tiers.

## 5. Qui achète, et pour quel prix

Un **MSP** qui doit brancher un agent d'éditeur chez un client dont la
cyber-sécurité refuse : la spécification du manifeste, la porte d'entrée et les
bornes sont un **produit** (`docs/MSP-PRICING.md`, `docs/PRIX-AGENTCORE.md`).

## 6. Si vous n'avez qu'une minute à y mettre

1. Ouvrez la démo, onglet **conformité** : la matrice dit ce qui est couvert,
   ce qui ne l'est pas, et **quel test** prouve chaque ligne.
2. Lisez **une** attestation en entier (elle tient sur une page) : elle dit le
   verdict, la portée statistique, et ce que la signature ne couvre pas.
3. Regardez `docs/ECHECS.md` : dix points où le projet ne va pas plus loin que
   ce qu'il prouve. C'est la partie qui mérite votre confiance.

## 7. Ce que le projet demande au jury

Rien de gratuit : ni l'accès à un compte client, ni une démo commerciale.
Si le dossier est convaincant, le vrai test reste **un agent d'éditeur réel
dans un environnement réel** — c'est le prolongement naturel de ce qui est
livré ici, et le sujet du cas d'usage à signer (`docs/narratif/`).
