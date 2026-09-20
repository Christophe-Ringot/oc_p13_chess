# Étude de faisabilité : Analyse du contenu des vidéos YouTube

## 1. Contexte et périmètre actuel

L'application recommande aujourd'hui des vidéos YouTube pertinentes pour
l'ouverture identifiée. Cette intégration se limite strictement aux
**métadonnées** exposées par l'API YouTube Data v3 :

- recherche (`search.list`) par mots-clés (`"<ouverture> chess opening
tutorial explanation"`),
- récupération du nombre de vues (`videos.list`) pour trier les résultats,
- affichage côté frontend du titre, de la chaîne et de la vignette, avec un
  lien vers la vidéo.

**Le contenu réel des vidéos (audio, transcription, image) n'est ni
téléchargé, ni analysé, ni indexé.** La vidéo n'intervient pas dans le RAG :
seul le corpus texte Wikichess alimente la recherche vectorielle Milvus et la synthèse Mistral.

Cette étude évalue la faisabilité d'aller plus loin : exploiter le **contenu**
des vidéos (transcription, éventuellement timestamps) comme source
supplémentaire du RAG, pour que l'agent puisse citer des explications de créateurs de contenu et renvoyer l'utilisateur vers le moment précis d'une
vidéo plutôt que vers la vidéo entière.

## 2. Architecture proposée

```
YouTube Data API (search.list)
        │  video_id, titre, chaîne
        ▼
Récupération de la transcription
   ├─ 1) Sous-titres existants (YouTube Transcript API / captions.list)
   └─ 2) Fallback ASR (Whisper) si aucun sous-titre disponible
        │  texte horodaté (timestamp → segment)
        ▼
Nettoyage / chunking temporel
   (regroupement de segments par fenêtre de ~30-60s ou par changement de sujet)
        │
        ▼
Embedding (même modèle que Wikichess : sentence-transformers,
Qwen3-Embedding, pour rester dans le même espace vectoriel)
        │
        ▼
Milvus — nouvelle collection `chess_videos` (ou champ `source_type` dans la
collection existante) avec les champs :
   embedding, text, opening, video_id, start_seconds, channel, source
        │
        ▼
search_milvus (rag_graph.py) fusionne les résultats Wikichess + vidéos
(par score, ou par pondération configurable par source)
        │
        ▼
Synthèse Mistral : prompt enrichi pour citer la source
(« d'après tel article » / « à X:XX dans telle vidéo »)
        │
        ▼
Frontend : lien vidéo avec paramètre `&t=<seconds>` pointant directement sur
le passage cité
```

### Pipeline d'ingestion (offline, périodique)

Contrairement à Wikichess (corpus statique, indexé une fois), le catalogue de
vidéos évolue en continu (nouvelles vidéos, vues qui changent). Il faut donc
un job d'ingestion **récurrent** (ex. tâche planifiée hebdomadaire) plutôt
qu'un script ponctuel :

1. Lister les vidéos déjà recommandées pour chaque ouverture (ou une liste
   blanche de chaînes de confiance : GothamChess, Hanging Pawns, Chessbrah…).
2. Récupérer leur transcription.
3. Chunker, vectoriser, upsert dans Milvus (déduplication par `video_id`).
4. Ignorer/retirer les vidéos dont la transcription est absente et dont le
   coût ASR dépasserait le budget alloué (voir §4).

## 3. Bénéfices attendus

- **Richesse du contenu** : les vidéos de titrés/streamers couvrent des
  nuances, des pièges pratiques et des parties commentées que les articles
  Wikichess (plus encyclopédiques) n'abordent pas toujours.
- **Fraîcheur** : une nouvelle idée théorique popularisée récemment
  apparaît sur YouTube bien avant d'être mise à jour dans un article de
  référence.
- **Expérience utilisateur** : citer un timestamp précis (« regardez à
  4:12 ») est plus actionnable qu'un simple lien vers une vidéo de 20
  minutes.
- **Diversité des sources** : réduit la dépendance à un corpus Wikichess
  limité à 9 ouvertures ; les vidéos couvrent un nombre de variantes bien
  plus large.

## 4. Limites et risques

| Sujet                             | Détail                                                                                                                                                                                                                                                                                                                                                                             |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Qualité de la transcription**   | Les sous-titres auto-générés YouTube gèrent mal le vocabulaire d'échecs (notation algébrique parlée, noms d'ouvertures, anglicismes) : taux d'erreur significatif sans retraitement.                                                                                                                                                                                               |
| **Disponibilité des sous-titres** | Toutes les vidéos n'ont pas de sous-titres (auteur ou auto) fiables ; le fallback ASR (Whisper) est nécessaire mais coûteux (temps + argent, cf. §5).                                                                                                                                                                                                                              |
| **Fiabilité du contenu**          | Une vidéo YouTube n'est pas relue/éditée comme un article Wikichess : risque d'erreurs théoriques, d'avis contradictoires entre créateurs, de contenu putclick sans rapport réel avec l'ouverture.                                                                                                                                                                                 |
| **Droits d'usage / CGU YouTube**  | Les CGU YouTube encadrent strictement le téléchargement et la réutilisation de contenu. Stocker des transcriptions complètes à long terme dans une base tierce est en zone grise ; il faut se limiter à de courts extraits utilisés en citation (fair use), ne jamais republier la vidéo elle-même, et prévoir la suppression des extraits si la vidéo est retirée par son auteur. |
| **Dérive du corpus**              | Sans curation (liste blanche de chaînes), le RAG peut remonter du contenu de mauvaise qualité mieux référencé (SEO) que pertinent.                                                                                                                                                                                                                                                 |
| **Complexité opérationnelle**     | Ajoute un pipeline d'ingestion récurrent, une nouvelle collection Milvus, une logique de fusion multi-source dans `rag_graph.py`, et un job de maintenance (vidéos supprimées/rendues privées).                                                                                                                                                                                    |
| **Latence**                       | La récupération de transcription à la volée (sans pré-indexation) ajouterait plusieurs secondes à chaque requête ; seule une indexation offline préalable permet de rester compatible avec le flux SSE actuel.                                                                                                                                                                     |

## 5. Estimation des coûts

Hypothèse de dimensionnement : 10 vidéos par ouverture, 9 ouvertures
aujourd'hui , durée moyenne 12 minutes.

| Poste                                                                               | Estimation                                                                                                                                                                                                  | Remarque                                                                                                                                                                                            |
| ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Quota YouTube Data API**                                                          | `search.list` = 100 unités, `videos.list` ≈ 1 unité/vidéo, `captions.list`/`captions.download` ≈ 200-250 unités par vidéo si sous-titres officiels récupérés via l'API                                      | Quota gratuit par défaut : 10 000 unités/jour → suffisant pour quelques dizaines de vidéos/jour, insuffisant pour un ré-indexage massif ponctuel sans étalement ou demande de quota supplémentaire. |
| **Transcription via bibliothèque tierce non officielle** (`youtube-transcript-api`) | Gratuit                                                                                                                                                                                                     | Ne consomme pas le quota API, mais est un usage non garanti par YouTube (peut casser sans préavis) — à traiter comme un best effort, pas une dépendance critique.                                   |
| **ASR de secours (Whisper)**                                                        | API managée : ≈ 0,006 $/minute → 90 vidéos × 12 min ≈ 1080 min ≈ **6,5 $** pour un premier remplissage ; auto-hébergé (`faster-whisper` sur CPU/GPU) : coût infrastructure (GPU) mais pas de coût à l'usage | À réserver aux vidéos sans sous-titres, pas en volumétrie systématique.                                                                                                                             |
| **Embeddings**                                                                      | Modèle déjà auto-hébergé (`sentence-transformers`, CPU) → coût marginal ≈ temps de calcul uniquement, pas de coût API                                                                                       | Volumétrie : quelques centaines de chunks supplémentaires, négligeable face au calcul déjà fait pour Wikichess.                                                                                     |
| **Stockage Milvus**                                                                 | Négligeable (quelques Mo de vecteurs supplémentaires)                                                                                                                                                       | Infra déjà provisionnée pour Wikichess.                                                                                                                                                             |
| **LLM Mistral (synthèse)**                                                          | Légère hausse du nombre de tokens de contexte par requête (citations vidéo en plus)                                                                                                                         | Impact marginal sur le coût par requête, modèle déjà utilisé.                                                                                                                                       |
| **Développement / maintenance**                                                     | Effort d'ingénierie non négligeable : pipeline d'ingestion planifié, gestion des CGU, curation de chaînes, tests                                                                                            | Coût humain plus significatif que le coût d'infrastructure pour ce périmètre.                                                                                                                       |

## 6. Recommandation

L'analyse du contenu vidéo est **techniquement faisable** avec les briques
déjà en place (mêmes services d'embedding et de vector store que Wikichess),
mais représente un effort d'ingénierie et de maintenance disproportionné par
rapport au périmètre actuel du projet (9 ouvertures, corpus texte
suffisant) :

- Le principal goulot n'est pas la recherche vectorielle mais la **qualité et
  la fiabilité des transcriptions** (sous-titres imparfaits, ASR coûteux) et
  la **gouvernance du contenu** (CGU YouTube, curation des sources).
- Le bénéfice utilisateur (citation d'un timestamp précis) est réel mais
  incrémental par rapport à l'existant (lien vers la vidéo déjà proposé).

**Recommandation : ne pas implémenter cette extension dans le périmètre
actuel.** Si le corpus Wikichess venait à devenir un facteur limitant (plus
d'ouvertures, demande de contenu plus pointu), une approche progressive est
suggérée :

1. **Phase 1 (faible risque/coût)** : se limiter aux sous-titres officiels
   d'une liste blanche restreinte de chaînes de confiance, sans ASR, extraits
   courts uniquement (quelques phrases par segment, jamais la transcription
   complète stockée).
2. **Phase 2 (si Phase 1 est concluante)** : ajouter l'ASR de secours pour
   les vidéos sans sous-titres, avec un budget mensuel plafonné.
3. **Phase 3 (optionnelle)** : job d'ingestion périodique automatisé avec
   monitoring de qualité (échantillonnage manuel des extraits indexés).
