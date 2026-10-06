# Étude de faisabilité : recherche de position exacte dans les vidéos d'échecs par vision par ordinateur et serveur MCP

## 1. Contexte et vision cible

### 1.1 Limite du système actuel

L'agent recommande aujourd'hui des vidéos YouTube pertinentes pour l'ouverture identifiée, par une recherche textuelle par mots-clés (`"<ouverture> chess opening tutorial explanation"`) suivie d'un tri par nombre de vues. Cette approche a une limite structurelle : elle ne sait retrouver qu'une vidéo entière en rapport avec une ouverture nommée, jamais un instant précis correspondant à la position réellement jouée par l'utilisateur.

Concrètement, un jeune joueur qui atteint une position après 6 coups dans une Sicilienne se voit aujourd'hui proposer une vidéo de 45 minutes sur « la Sicilienne » en général, sans savoir si et à quel moment cette position précise y est traitée. Il doit visionner ou avancer manuellement dans la vidéo pour trouver le passage utile, ce qui casse l'expérience d'entraînement position par position que l'agent propose par ailleurs pour la théorie (Lichess) et l'évaluation (Stockfish).

### 1.2 Objectif de la solution étudiée

Alan propose de fermer cet écart en indexant les vidéos au niveau de la position d'échecs elle-même, et non plus seulement au niveau de leurs métadonnées ou de leur transcription textuelle :

1. Stocker un catalogue de vidéos pertinentes (chaînes reconnues, vidéos déjà recommandées par le système actuel).
2. Extraire des frames (images) de chaque vidéo à intervalle régulier ou par détection de changement de plan.
3. Sur chaque frame, détecter la présence d'un échiquier et, si détecté, convertir la position affichée en notation FEN grâce à un modèle de vision (approche dite board-to-FEN).
4. Indexer le triplet `(FEN, video_id, timestamp)` pour permettre une recherche par position exacte : à partir du FEN de la position jouée par l'utilisateur, retrouver les vidéos qui montrent cette même position et renvoyer un lien avec le timestamp précis (`&t=<secondes>`).
5. Exposer cette capacité de recherche via un serveur MCP (Model Context Protocol), pour la rendre consommable facilement par l'agent LangGraph existant, et par d'autres clients futurs de la FFE sans dupliquer la logique.

Cette étude évalue la faisabilité technique, les bénéfices, les limites et les coûts de ce système, sans l'implémenter : c'est un livrable de conception destiné à appuyer la démonstration du POC et à éclairer une décision d'investissement ultérieure.

## 2. Panorama technologique : détection d'échiquier et conversion en FEN

La conversion d'une image d'échiquier en FEN (« board-to-FEN ») est un problème de vision par ordinateur étudié depuis plusieurs années, avec deux familles d'approches complémentaires.

### 2.1 Approche classique (traitement d'image, OpenCV)

1. Détection des contours et des coins de l'échiquier : recherche de lignes dominantes (transformée de Hough), détection de coins (Harris, ou coins d'un damier via `cv2.findChessboardCorners`, conçu à l'origine pour la calibration de caméra mais réutilisable sur un échiquier régulier), ou segmentation par couleur/contraste pour les échiquiers logiciels (rendu net, contours francs).
2. Correction de perspective (homographie) : une fois les 4 coins identifiés, une transformation homographique (`cv2.warpPerspective`) redresse l'échiquier en vue de dessus parfaitement carrée.
3. Découpage en 64 cases : l'image redressée est simplement divisée en une grille 8×8 régulière.
4. Classification par case : chaque case (vide, ou l'une des 12 combinaisons pièce/couleur) est classifiée, historiquement par un classifieur simple (template matching, SVM sur descripteurs HOG), aujourd'hui quasi systématiquement par un petit CNN.

Cette approche classique est robuste et peu coûteuse en calcul, mais fragile face à la variabilité visuelle réelle des vidéos YouTube : angle de caméra sur un échiquier physique, reflets, main du joueur qui occulte des cases, curseur ou overlay graphique par-dessus un échiquier logiciel, styles de pièces et de plateau très variés (bois, plastique, thèmes Lichess/Chess.com personnalisés).

### 2.2 Approche par apprentissage profond (deep learning)

Les systèmes récents combinent :

- un modèle de détection/segmentation de l'échiquier dans l'image complète (au lieu de supposer qu'il occupe tout le cadre), utile car en vidéo YouTube l'échiquier n'occupe souvent qu'une partie de l'écran (webcam du streamer, overlay, incrustations) ;
- un CNN de classification par case (généralement 13 classes : case vide + 6 types de pièce × 2 couleurs), entraîné sur des jeux de données annotés d'échiquiers réels et rendus logiciels ;
- parfois une approche end-to-end par détection d'objets (type YOLO) qui détecte directement chaque pièce et sa position sur le plateau plutôt que de classifier case par case, plus robuste aux pièces qui débordent légèrement de leur case.

### 2.3 Travaux et projets de référence à étudier

Sans que ce soit exhaustif ni une recommandation définitive, plusieurs pistes de recherche existent et méritent d'être évaluées avant un choix d'implémentation :

- des projets communautaires open source de classification d'échiquier par CNN par case (recherche GitHub : « chessboard recognition CNN », « tensorflow chessbot »), qui donnent un ordre de grandeur de précision atteignable avec un pipeline classique + CNN léger sur des échiquiers rendus numériquement ;
- des travaux académiques plus récents sur la reconnaissance complète d'état de jeu d'échecs à partir d'une image unique, avec jeux de données dédiés à la reconnaissance d'échiquiers physiques photographiés sous conditions variées (utile pour évaluer la difficulté du cas « échiquier physique filmé », plus dur que le cas « overlay logiciel ») ;
- des jeux de données et modèles de détection de pièces d'échecs de type YOLO disponibles sur les plateformes communautaires de vision par ordinateur (Roboflow Universe et équivalents), utilisables comme point de départ pour du transfer learning plutôt qu'un entraînement from scratch ;
- des services de vision managés génériques (Google Cloud Vision, Azure Computer Vision) : ils ne proposent pas de détection d'échiquier prête à l'emploi (ce n'est pas une classe standard), mais leurs offres d'AutoML Vision (entraînement d'un modèle de classification/détection sur un jeu de données propriétaire) sont une alternative à l'entraînement d'un modèle en interne, à évaluer sur le rapport coût/précision.

Recommandation méthodologique : avant tout engagement de développement, mener un spike technique (voir §8) consistant à mesurer la précision d'un pipeline classique + CNN léger sur un échantillon réel de 20 à 30 vidéos représentatives du catalogue cible (mélange overlay logiciel / échiquier physique), afin de disposer d'un chiffre de précision mesuré plutôt qu'estimé.

### 2.4 Limites intrinsèques de la reconstruction FEN depuis une image

Un point de vigilance technique fondamental, à anticiper dès la conception : une notation FEN complète contient des informations qui ne sont pas visibles sur une image statique.

| Champ du FEN                         | Récupérable depuis l'image ?                                                                                           |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| Placement des pièces (les 8 rangées) | Oui, c'est l'objet même de la détection                                                                                |
| Trait (qui doit jouer)               | Non directement, mais déductible en comparant deux frames consécutives (le camp qui vient de bouger n'a plus le trait) |
| Droits de roque                      | Non, nécessite l'historique de la partie, pas seulement la position                                                   |
| Prise en passant                     | Non, nécessite de savoir si le dernier coup était une avancée de pion de deux cases                                   |
| Compteurs de demi-coups / coups      | Non, nécessite l'historique complet                                                                                    |

Conséquence directe sur l'architecture : le système ne peut produire de manière fiable qu'un FEN de placement des pièces (le premier champ), pas un FEN complet au sens strict. La recherche de « position exacte » proposée doit donc être conçue comme une recherche sur le placement des pièces uniquement, ce qui est suffisant pour le cas d'usage (« montre-moi où cette disposition de pièces apparaît dans une vidéo ») mais doit être documenté clairement pour ne pas laisser croire à une reconstruction FEN parfaite.

## 3. Architecture technique proposée

### 3.1 Principes directeurs

- Découplage total du pipeline vidéo (lourd, GPU, asynchrone, périodique) et de l'application principale (FastAPI/LangGraph, légère, synchrone) : ils ne doivent pas partager de cycle de vie ni de ressources de calcul.
- Indexation offline, recherche online : l'extraction de frames et la détection sont coûteuses et s'exécutent en tâche de fond planifiée ; la recherche d'une position dans l'index déjà construit doit rester rapide (quelques dizaines de millisecondes).
- Interopérabilité par MCP plutôt que par un couplage direct à l'agent LangGraph existant (voir §3.4).
- Modularité : chaque étape du pipeline (extraction, détection, classification, indexation) est un composant remplaçable indépendamment ; un futur modèle de classification plus précis doit pouvoir remplacer l'existant sans toucher au reste du pipeline.

### 3.2 Pipeline d'ingestion offline

Contrairement au corpus Wikichess (statique, indexé une fois), le catalogue vidéo évolue en continu. Le pipeline est donc conçu comme un job batch périodique (ex. hebdomadaire), pas comme un traitement à la demande :

1. Sélection du catalogue : liste blanche de chaînes de confiance (curée manuellement, à l'image de ce que fait déjà la FFE pour d'autres contenus pédagogiques) ou vidéos déjà recommandées par le système de recherche textuel actuel.
2. Téléchargement temporaire de la vidéo (outil de type `yt-dlp`), traitée puis supprimée : aucun stockage long terme du fichier vidéo lui-même (voir limites juridiques, §5.2).
3. Échantillonnage de frames : extraction à fréquence fixe (ex. 1 image/2 secondes) ou, plus efficacement, par détection de changement de plan (une position d'échecs affichée à l'écran reste stable plusieurs secondes ; un changement de plan brutal indique un nouveau contenu à analyser), ce qui réduit fortement le volume de frames à traiter par rapport à un échantillonnage naïf.
4. Détection d'échiquier : filtre la grande majorité des frames (intro, visage du présentateur, publicité, montage) ne contenant pas d'échiquier exploitable.
5. Redressement et découpage en 64 cases (§2.1).
6. Classification par case, ce qui donne une grille 8×8 de pièces, avec un score de confiance.
7. Assemblage du FEN de placement, déduction du trait par différence avec la frame valide précédente, puis validation de cohérence via `python-chess` (rejet des placements structurellement invalides, ex. plus de deux rois).
8. Déduplication temporelle : les frames consécutives donnant le même FEN sont fusionnées en un seul segment `(fen, t_debut, t_fin)`, pour éviter d'indexer des centaines de doublons quasi identiques.
9. Écriture dans l'index de positions.

### 3.3 Modèle de données / index de positions

Une base documentaire (MongoDB, cohérente avec la brique déjà prévue dans le socle technique du projet) convient bien à ce cas d'usage : documents hétérogènes, pas de jointures complexes, volumétrie modérée.

```
collection video_positions
{
  video_id: "abc123",
  channel: "GothamChess",
  title: "...",
  fen_placement: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR",
  side_to_move: "w" | "b" | null,   // null si non déductible
  t_start_seconds: 312,
  t_end_seconds: 341,
  confidence: 0.87,
  detector_version: "v1.2",
  indexed_at: ISODate(...)
}
```

La recherche « position exacte » se fait sur le champ `fen_placement` (égalité stricte, éventuellement avec une tolérance sur quelques cases pour absorber les erreurs de classification, voir §5.1) : un index simple (hash ou index composé Mongo) suffit, pas besoin d'une base vectorielle pour cet usage précis, contrairement à la recherche sémantique texte déjà en place sur Wikichess dans Milvus. C'est un point important : ce sous-système n'est pas un doublon de la brique RAG existante, il répond à un besoin de correspondance exacte, pas de similarité sémantique.

### 3.4 Pourquoi un serveur MCP

Le choix d'exposer ce système via un serveur MCP plutôt que de l'intégrer directement comme un nouveau service FastAPI interne répond à plusieurs objectifs :

- Découplage d'infrastructure : le pipeline de vision (GPU, dépendances lourdes : OpenCV, modèle de classification, éventuellement `yt-dlp`) peut être développé, déployé et mis à l'échelle indépendamment de l'API principale, par une équipe ou un cycle de release distinct.
- Réutilisabilité : un serveur MCP expose ses capacités (« outils ») de façon standardisée, découvrable par n'importe quel client compatible MCP, pas seulement l'agent LangGraph actuel. La FFE pourrait, par exemple, réutiliser ce même serveur depuis un futur outil interne d'analyse de contenu, sans réécrire l'intégration.
- Interface stable côté agent : côté application principale, un seul appel d'outil MCP (`search_position`) remplace ce qui serait sinon un client HTTP dédié avec sa propre gestion d'erreurs/timeouts, cohérent avec la manière dont l'agent LangGraph orchestre déjà des outils hétérogènes (Lichess, Stockfish, Milvus, YouTube).
- Évolutivité contrôlée : le contrat d'outil (schéma d'entrée/sortie MCP) peut rester stable même si l'implémentation interne du pipeline de détection change complètement (nouveau modèle, nouvelle approche).

Le principal outil exposé serait :

- `search_position(fen_placement: str, tolerance: int = 0) -> list[{video_id, title, channel, url, t_seconds, confidence}]`

complété par un outil utilitaire `get_video_timeline(video_id: str)` pour l'inspection/débogage, et une ressource `index_stats` (nombre de vidéos et de positions indexées, date de dernière mise à jour) utile pour le monitoring.

### 3.5 Schéma d'architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  PIPELINE D'INGESTION OFFLINE (job batch périodique, ex. hebdo)      │
│                                                                        │
│   Catalogue de chaînes            yt-dlp                             │
│   (liste blanche, curée) ───▶ Téléchargement temporaire               │
│                                       │ fichier vidéo (éphémère)       │
│                                       ▼                                │
│                            Frame Sampler (ffmpeg/OpenCV)               │
│                              - échantillonnage temporel ou             │
│                                détection de changement de plan         │
│                                       │ frames candidates               │
│                                       ▼                                │
│                            Board Detector (CV / segmentation)          │
│                              - localise l'échiquier, rejette le reste  │
│                                       │ frame + 4 coins                 │
│                                       ▼                                │
│                     Perspective Warp + découpage en 64 cases           │
│                                       │                                 │
│                                       ▼                                │
│                     Piece Classifier (CNN, 13 classes/case)            │
│                                       │ grille 8x8 + confiances         │
│                                       ▼                                │
│              FEN Builder + validation (python-chess) + dédup temporel  │
│                                       │                                 │
│                                       ▼                                │
│              ┌─────────────────────────────────────────┐              │
│              │   MongoDB — collection video_positions   │              │
│              └─────────────────────────────────────────┘              │
└────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌────────────────────────────────────────────────────────────────────┐
│  SERVEUR MCP  « chess-video-positions »                              │
│                                                                        │
│   Tool  search_position(fen_placement, tolerance?)                    │
│         → interroge video_positions, retourne les meilleurs matches   │
│   Tool  get_video_timeline(video_id)                                  │
│   Resource  index_stats                                               │
└────────────────────────────────────────────────────────────────────┘
                                       │  MCP (stdio ou HTTP/SSE)
                                       ▼
┌────────────────────────────────────────────────────────────────────┐
│  Agent LangGraph existant (client MCP)                                │
│    Nouveau nœud `search_video_position` :                             │
│      appelle le tool MCP `search_position` avec le FEN de la          │
│      position en cours (déjà présent dans le state de l'agent) —      │
│      en complément du nœud `search_videos` (recherche par mot-clé)    │
│      déjà en place, pas en remplacement                               │
└────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌────────────────────────────────────────────────────────────────────┐
│  Frontend Angular                                                     │
│    Lien vidéo enrichi d'un paramètre `&t=<t_seconds>` pointant         │
│    directement sur le passage où la position exacte apparaît          │
└────────────────────────────────────────────────────────────────────┘
```

### 3.6 Intégration avec l'agent existant

Le nœud `search_video_position` s'ajouterait au graphe LangGraph décrit dans le POC (`backend/app/services/rag_graph.py`) en parallèle du nœud `search_videos` déjà existant, dans la branche déclenchée uniquement lorsqu'une position théorique est identifiée. Les deux résultats (recherche par mot-clé et recherche par position exacte) seraient présentés distinctement côté frontend : le premier pour découvrir des ressources générales sur l'ouverture, le second pour un lien direct « cette position précise est expliquée ici ».

## 4. Bénéfices attendus

- Précision pédagogique : au lieu d'une vidéo de 45 minutes, l'utilisateur reçoit un lien pointant sur les quelques secondes où sa position est effectivement discutée, un gain d'expérience directement aligné sur l'objectif d'entraînement position par position de l'agent.
- Valorisation du contenu existant : des vidéos déjà indexées par mots-clés révèlent une valeur supplémentaire (chaque position qu'elles montrent devient individuellement retrouvable), sans effort de production de contenu nouveau.
- Différenciation produit : peu d'outils grand public proposent une recherche de position exacte dans un catalogue vidéo ; c'est un argument de démonstration fort pour la FFE face aux fédérations homologues ou aux partenaires.
- Réutilisabilité au-delà du POC : le serveur MCP, une fois construit, est un actif technique indépendant, potentiellement réutilisable pour d'autres besoins de la FFE (analyse de parties de tournois filmées, indexation de conférences techniques, etc.).

## 5. Limites et risques

### 5.1 Risques techniques

| Risque                                          | Détail                                                                                                                                                                                                                                                                                                     | Sévérité                             |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| Robustesse de la détection selon le format vidéo | Un échiquier logiciel (overlay Lichess/Chess.com, rendu net, vue de dessus) est un problème de vision nettement plus simple qu'un échiquier physique filmé (angle, éclairage, reflets, main du joueur, qualité de webcam). Traiter les deux avec un seul modèle dès le départ est risqué.               | Élevée                               |
| FEN partiel                                      | Comme détaillé en §2.4, seul le placement des pièces est reconstruit de façon fiable ; la recherche doit être conçue en conséquence, pas comme un FEN complet.                                                                                                                                          | Moyenne (maîtrisable par conception) |
| Erreurs de classification silencieuses           | Une pièce mal classifiée (ex. confusion fou/pion à faible résolution) produit un FEN incorrect qui peut malgré tout sembler plausible et polluer l'index sans erreur explicite. Nécessite un seuil de confiance strict et une tolérance de recherche (§3.3) plutôt qu'une égalité stricte systématique. | Moyenne-élevée                       |
| Faux positifs de détection d'échiquier           | Diagrammes de puzzle, position d'une autre partie évoquée en incrustation, ou échiquier affiché sans rapport avec la partie commentée à l'instant T, peuvent être indexés à tort.                                                                                                                       | Moyenne                              |
| Volume de calcul de l'échantillonnage naïf       | Sans détection de changement de plan, le nombre de frames à traiter croît linéairement avec la durée du catalogue et peut vite devenir le poste de coût dominant (§6.2).                                                                                                                                | Moyenne (maîtrisable par conception) |
| Dérive du modèle dans le temps                   | Nouveaux thèmes visuels de plateformes (Lichess/Chess.com changent occasionnellement leurs jeux de pièces par défaut), nouvelles chaînes avec des styles différents : le modèle nécessite un ré-entraînement ou un enrichissement périodique du jeu de données.                                         | Moyenne                              |

### 5.2 Risques business et juridiques

| Risque                                    | Détail                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CGU YouTube                               | Le téléchargement de vidéos, même temporaire, et la réutilisation dérivée de leur contenu (frames analysées) doivent rester strictement conformes aux CGU de la plateforme : pas de republication, pas de stockage long terme du contenu source, suppression immédiate du fichier vidéo après extraction des frames utiles. Ce point, déjà identifié pour l'approche par transcription, s'applique aussi ici et doit être validé juridiquement avant tout déploiement au-delà d'un prototype interne. |
| Gouvernance du catalogue                  | Sans curation stricte (liste blanche de chaînes), le système peut indexer du contenu de qualité inégale ou hors sujet.                                                                                                                                                                                                                                                                                                                                                                                |
| ROI incertain à ce stade                  | La valeur ajoutée réelle (impact sur l'engagement/l'apprentissage des jeunes joueurs) n'est pas mesurée : c'est une hypothèse produit qui mérite d'être testée à petite échelle avant un investissement complet (voir alternatives, §7).                                                                                                                                                                                                                                                              |
| Dépendance à un outil tiers non garanti   | Les outils de téléchargement vidéo tiers (type `yt-dlp`) ne sont pas officiellement supportés par YouTube et peuvent cesser de fonctionner sans préavis en cas de changement côté plateforme, à traiter comme un maillon fragile de la chaîne, pas une dépendance de production critique sans plan de repli.                                                                                                                                                                                         |

## 6. Estimation des coûts

Les estimations ci-dessous sont des ordres de grandeur destinés à éclairer une décision d'investissement, pas un chiffrage d'engagement contractuel. Hypothèse de dimensionnement initial : catalogue de 50 chaînes de confiance, environ 500 vidéos indexées au lancement, durée moyenne 12 minutes, avec une croissance d'environ 50 vidéos/mois ensuite.

### 6.1 Coûts de build (CAPEX)

| Lot de travail                                                                          | Estimation (jours-homme) | Détail                                                                                                                            |
| ----------------------------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ |
| Spike technique (mesure de précision sur échantillon réel)                              | 4-5 j                    | Prérequis avant tout engagement plus large, voir §8                                                                              |
| Pipeline d'ingestion (téléchargement, échantillonnage, détection de changement de plan) | 4-5 j                    | Intégration `yt-dlp`/`ffmpeg`, gestion des erreurs, suppression des fichiers temporaires                                          |
| Détection d'échiquier + correction de perspective                                       | 5-6 j                    | Selon que l'approche classique suffise ou qu'un entraînement/fine-tuning soit nécessaire                                          |
| Classification des pièces (CNN)                                                         | 6-8 j                    | Réutilisation d'un modèle existant + fine-tuning, ou entraînement dédié si aucun modèle réutilisable n'atteint la précision cible |
| Assemblage FEN + validation + déduplication                                             | 3 j                       | Logique métier, intégration `python-chess`                                                                                        |
| Modèle de données + index MongoDB                                                       | 2-3 j                    |                                                                                                                                     |
| Serveur MCP (outils, schémas, gestion des erreurs)                                      | 4-5 j                    |                                                                                                                                     |
| Intégration côté agent LangGraph + frontend (lien timestamp)                            | 3-4 j                    |                                                                                                                                     |
| Jeu d'évaluation de précision + tuning des seuils de confiance                          | 4 j                       | Sur le modèle de `scripts/evaluate_rag.py` déjà en place pour le RAG texte                                                        |
| Total                                                                                    | ≈ 35-43 j-homme          | Soit environ 7 à 9 semaines à un ETP, ou 4 à 5 semaines à deux ETP en parallèle                                                   |

À un TJM (taux journalier moyen) indicatif de 500-600 € pour un profil ingénierie/vision par ordinateur en France, cela représente un budget de développement de l'ordre de 18 000 € à 26 000 €, hors coûts d'infrastructure de développement (calcul GPU pour l'entraînement/fine-tuning, de l'ordre de quelques centaines d'euros sur un service cloud à la demande pour cette volumétrie).

### 6.2 Coûts d'exploitation (OPEX, récurrents)

| Poste                                       | Estimation                                                                                                                                                                                                                                                                                                                                                      | Remarque                                                                                                             |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| Calcul, indexation initiale du catalogue    | Avec détection de changement de plan (plutôt qu'échantillonnage fixe), de l'ordre de quelques dizaines de milliers de frames à traiter pour 500 vidéos. Sur GPU cloud à la demande (type instance T4, environ 0,35-0,50 $/h), le traitement complet se compte en quelques heures de calcul, soit de l'ordre de quelques dizaines d'euros pour le remplissage initial. | Dominé par le coût du téléchargement/décodage vidéo plus que par l'inférence elle-même                               |
| Calcul, mise à jour périodique              | Environ 50 nouvelles vidéos/mois, une volumétrie mensuelle très inférieure au remplissage initial, de l'ordre de quelques euros/mois de calcul                                                                                                                                                                                                                  | À planifier en tâche de fond hors heures de pointe                                                                   |
| Stockage                                    | Frames non conservées après extraction du FEN (seule la donnée structurée est indexée), stockage négligeable. Si conservation d'un échantillon de frames pour audit qualité : quelques Go, coût négligeable.                                                                                                                                                   | Décision de conception à trancher tôt (voir §8)                                                                      |
| Base MongoDB                                | Volumétrie modeste (quelques centaines de milliers de documents au maximum), coût d'hébergement marginal, réutilise l'infrastructure déjà provisionnée pour le reste du socle applicatif                                                                                                                                                                       |                                                                                                                        |
| Hébergement serveur MCP                     | Petit service applicatif, coût marginal comparable à un des micro-services déjà en place (backend FastAPI)                                                                                                                                                                                                                                                      |                                                                                                                        |
| Maintenance et supervision                  | Effort humain récurrent : surveillance du taux de succès de détection, curation de la liste blanche de chaînes, ré-entraînement périodique du modèle en cas de dérive, veille sur la disponibilité de l'outil de téléchargement tiers                                                                                                                           | Poste dominant à moyen terme : à budgéter en temps ingénieur (ex. 1-2 j/mois) plutôt qu'en coût d'infrastructure     |

Synthèse : contrairement à l'approche par transcription/ASR étudiée initialement (où le coût principal était la transcription elle-même, facturée à la minute), le coût d'exploitation de cette approche par vision est dominé par le calcul GPU ponctuel et surtout par la maintenance humaine, pas par un coût variable par vidéo qui exploserait avec le volume. C'est un profil de coût plus favorable à long terme, à condition que la précision du modèle reste acceptable sans intervention constante.

### 6.3 Hypothèses et sensibilité

Ces estimations reposent sur l'hypothèse que la détection de changement de plan permet de limiter drastiquement le nombre de frames à traiter, et qu'un modèle de classification existant (réutilisé et affiné) suffit à atteindre une précision exploitable sur le cas d'usage « échiquier logiciel » sans entraînement complet from scratch. Si le spike technique (§8) révèle que ce n'est pas le cas, en particulier pour les échiquiers physiques filmés, le budget de build pourrait augmenter significativement (constitution d'un jeu de données annoté propre, entraînement plus lourd), ce qui renforce l'intérêt de restreindre le périmètre initial (voir alternative 2, §7).

## 7. Alternatives envisagées

### Alternative 1 : exploiter les chapitres/timestamps fournis par les créateurs (sans vision par ordinateur)

De nombreuses chaînes d'échecs structurent déjà leurs vidéos avec des chapitres YouTube (horodatage + titre) ou listent les coups joués dans la description. Une approche à coût quasi nul consisterait à parser ces métadonnées textuelles (déjà exposées par l'API YouTube Data) et à associer heuristiquement des segments temporels à des phases de partie, sans aucune analyse d'image.

- Avantages : coût de build et d'exploitation quasi nul, aucun risque de détection erronée, livrable en quelques jours.
- Limites : ne fonctionne que pour les chaînes qui structurent déjà leur contenu ainsi (couverture partielle du catalogue), granularité au mieux au niveau du coup annoncé dans une description, pas au niveau du FEN exact.
- Usage recommandé : un quick win à court terme, potentiellement complémentaire à long terme (fusionner les deux sources d'indexation), et un bon moyen de valider l'hypothèse produit (les utilisateurs cliquent-ils vraiment sur des liens horodatés ?) avant d'investir dans la vision par ordinateur.

### Alternative 2 : restreindre le périmètre initial aux échiquiers logiciels (overlay Lichess/Chess.com)

Plutôt que de viser dès le départ tous les formats vidéo (échiquiers physiques filmés inclus, nettement plus difficiles en vision par ordinateur, cf. §5.1), limiter la version 1 du système aux vidéos utilisant un overlay d'échiquier logiciel (rendu net, vue de dessus stable), qui représentent une part importante des vidéos de créateurs de contenu échiquéen (analyses de parties en ligne, streams).

- Avantages : réduit fortement la difficulté et donc le coût du lot « détection + classification » (§6.1), permet de livrer une v1 utile et de mesurer l'adoption avant d'investir dans le cas plus difficile de l'échiquier physique.
- Limites : exclut une partie du catalogue (vidéos filmées sur échiquier physique, format encore courant chez certains créateurs et pour le contenu de club/tournoi).
- Usage recommandé : approche privilégiée pour une première version si la décision est prise d'investir dans la vision par ordinateur, cohérent avec la recommandation générale de rester réaliste sur la complexité (voir points de vigilance de la mission).

## 8. Roadmap de développement

1. Phase 0, spike de faisabilité (1 semaine) : mesurer la précision réelle d'un pipeline classique + CNN léger réutilisé sur un échantillon de 20 à 30 vidéos représentatives (mélange overlay logiciel / physique). Décision go/no-go et arbitrage du périmètre (alternative 2) sur la base de chiffres mesurés, pas estimés.
2. Phase 1, MVP sur périmètre restreint (3-4 semaines) : pipeline d'ingestion + détection + classification limités aux échiquiers logiciels, index MongoDB, jeu d'évaluation de précision.
3. Phase 2, serveur MCP et intégration agent (1-2 semaines) : exposition des outils MCP, nouveau nœud LangGraph, affichage frontend du lien horodaté.
4. Phase 3, extension et industrialisation : élargissement au catalogue plus large (échiquiers physiques), automatisation complète du job d'ingestion périodique, tableau de bord de supervision (taux de détection, précision estimée, alerte sur dérive), curation continue de la liste blanche de chaînes.

## 9. Recommandation

Le système de recherche de position exacte par vision par ordinateur est techniquement faisable et s'appuie sur des briques matures (OpenCV, CNN de classification, `python-chess` déjà utilisé dans le POC, MongoDB déjà prévu au socle technique). Son profil de coût d'exploitation est favorable à long terme (dominé par la maintenance humaine plutôt que par un coût variable par vidéo).

Cependant, la difficulté et le coût réels dépendent fortement de la diversité des formats vidéo à couvrir dès le départ, un point qui ne peut être chiffré avec confiance sans un spike technique préalable.

Recommandation : ne pas engager le développement complet dans l'immédiat. Procéder en deux temps :

1. Valider l'hypothèse produit à coût quasi nul via l'alternative 1 (chapitres/timestamps déclaratifs), qui peut être livrée rapidement et donne un premier signal d'usage réel.
2. Si le signal est positif, lancer le spike technique de la Phase 0 pour chiffrer précisément la Phase 1, en restreignant le périmètre initial à l'alternative 2 (échiquiers logiciels) afin de maîtriser le risque technique et budgétaire avant d'envisager une extension aux échiquiers physiques.
