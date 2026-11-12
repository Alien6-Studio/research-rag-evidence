# Preuves et traçabilité

La collecte principale comprend **64 questions distinctes**, chacune évaluée dans
huit configurations, soit **512 réponses effectivement générées**. Il ne s’agit
pas de 512 questions indépendantes.

| Élément | Fichier ou dossier | Ce qu’il permet de vérifier |
| --- | --- | --- |
| Protocole antérieur aux mesures | [PROTOCOL.md](PROTOCOL.md), commit `abe5f87` | Questions, variables et critères prévus |
| Code exécuté | [run.py](run.py), empreinte dans le manifeste | Recherche, assemblage, appels et scores |
| Entrées figées | [sources.json](sources.json) | Révisions et empreintes du corpus et du tokenizer |
| Environnement | [requirements-lock.txt](requirements-lock.txt) | Versions Python des bibliothèques |
| Tests de contrôle | [test_run.py](test_run.py), neuf tests | Coordonnées des preuves, budgets et règles de score |
| Campagne principale | `runs/2026-11-12-rag/` | Questions sélectionnées, contextes, requêtes et réponses brutes |

Le manifeste contient l’empreinte intégrale du modèle, la version d’Ollama, les
paramètres, le commit source et l’heure de préparation. Chaque réponse conserve
sa requête, la sortie brute du service et les durées retournées par Ollama.

Les contrôles de génération, répétitions et jugements documentaires sont
enregistrés dans des fichiers séparés. Le jugement automatique est un indicateur
à contrôler, pas une annotation humaine. Les résultats agrégés seront publiés
avec le script qui les recalcule et les limites de la campagne.

Les données dérivées de HotpotQA sont attribuées à Yang, Qi, Zhang et al. (EMNLP
2018), sous CC BY-SA 4.0. Les empreintes garantissent l’identité des fichiers ;
l’interprétation scientifique dépend du protocole et des contrôles décrits.
