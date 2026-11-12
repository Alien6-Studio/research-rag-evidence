# Préservation des preuves dans une chaîne RAG

Recherche associée à l’article Alien6 conservé à l’URL
`/fr/research/articles/audit-architecture-rag/`.

**Question :** dans quelles conditions retrouver les bonnes sources conduit-il à
une réponse effectivement étayée ?

## État du travail

Le protocole est fixé avant collecte. Le benchmark et neuf tests de contrôle
sont préparés. **Aucune campagne de mesure n’a encore été exécutée.** Les chiffres
des anciens exemples synthétiques ne constituent pas les résultats de ce projet.

- [Protocole](PROTOCOL.md) : hypothèses, variables, mesures et limites.
- [Chaîne expérimentale](run.py) : segmentation, indexation, recherche BM25 et
  dense, sélection sous budget, génération Ollama, évaluation et contrôle du juge.
- [Tests](test_run.py) : coordonnées des preuves, budgets, absence d’utilisation
  des annotations par la sélection et règles de score.
- [Sources figées](sources.json) et [dépendances](requirements-lock.txt).
- `runs/` : configurations, sorties brutes et mesures de chaque campagne.

La première campagne porte sur 64 questions HotpotQA, soit 512 configurations de
génération. Elle utilise les dix paragraphes fournis pour chaque question dans
le cadre *distractor*, pas une recherche sur tout Wikipédia. Les modèles sont
servis localement par Ollama ; leurs empreintes sont vérifiées à l’exécution.

## Exécution

```bash
uv venv --python 3.12
uv pip install --python .venv/bin/python -r requirements-lock.txt
.venv/bin/python prepare_data.py
.venv/bin/python -m unittest discover -p 'test_*.py'
.venv/bin/python run.py prepare
.venv/bin/python run.py generate
.venv/bin/python run.py controls
.venv/bin/python run.py generate --repeat 1
.venv/bin/python run.py generate --repeat 2
.venv/bin/python run.py judge
```

Le modèle, les paramètres et les entrées doivent correspondre au protocole. Un
échec de format ou une abstention reste dans les mesures ; le programme ne
régénère pas une réponse pour obtenir un succès. Les données téléchargées et
l’environnement Python restent hors de Git. Les sorties d’expériences seront
conservées avec l’empreinte du code exécuté.

## Attribution

HotpotQA : Yang, Qi, Zhang et al., EMNLP 2018,
<https://hotpotqa.github.io/>, données sous CC BY-SA 4.0. Les questions, preuves
et extraits dérivés de ce corpus conservent cette attribution et cette licence.
Le script officiel d’évaluation est conservé sans modification dans `vendor/`,
avec sa licence Apache-2.0. Le tokenizer provient du dépôt officiel Qwen indiqué
dans `sources.json`.
