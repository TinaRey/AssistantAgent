# Déploiement : Render (application) + Supabase (base de données)

Deux services web Render (Docker) et une base Postgres Supabase :

```
Navigateur ─HTTPS─> pantalelle-app (Next.js) ─HTTPS + clé interne─> pantalelle-api (FastAPI) ─> Supabase (Postgres + pgvector)
```

Seul `pantalelle-app` est destiné aux utilisateurs. `pantalelle-api` est public techniquement (la formule gratuite
de Render ne permet pas de service privé), mais il **refuse tout appel qui ne porte pas la clé interne**.

> Ce guide suppose que le code à déployer est sur la branche `main` de votre dépôt GitHub (voir `render.yaml`,
> champ `branch`). Rien n'est déployé tant que vous n'avez pas créé le Blueprint sur Render.

## Avant de commencer

- [ ] Le code voulu est fusionné et poussé sur `main` (y compris `render.yaml`, `backend/Dockerfile`, `frontend/Dockerfile`).
- [ ] Vous avez des comptes : GitHub, [Render](https://render.com), [Supabase](https://supabase.com), OpenAI (clé API avec limite de dépense), Tavily (facultatif).
- [ ] Vous avez choisi le mot de passe d'accès de l'application (long : 12 caractères ou plus).

## 1. Supabase (base de données)

1. *New project*, région **Frankfurt (eu-central-1)**, un mot de passe de base solide (notez-le).
2. Cliquez sur **Connect** > **Session pooler** et copiez l'URI (`postgresql://postgres.<ref>:<mot de passe>@aws-…pooler.supabase.com:5432/postgres`).
   - Utilisez le **Session pooler**, pas la connexion directe : la connexion directe de Supabase n'est pas joignable en IPv4 sans option payante et je n'ai pas pu confirmer que Render sorte en IPv6 (à vérifier si la connexion échoue).
   - Ajoutez `?sslmode=require` à la fin de l'URL.
   - Collez-la telle quelle : l'application convertit `postgresql://` en `postgresql+psycopg://`.
3. L'extension `vector` est activée automatiquement par la première migration. Si Supabase la refuse, activez-la dans *Database > Extensions*.

## 2. Secrets

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # -> INTERNAL_API_KEY (à coller sur LES DEUX services)
```

`SECRET_KEY` est généré par Render. Ne mettez jamais ces valeurs dans le dépôt.

## 3. Render

1. *New* > **Blueprint**, choisissez le dépôt : Render lit `render.yaml` et crée `pantalelle-api` et `pantalelle-app` (région Frankfurt).
2. Renseignez les valeurs demandées :

| Variable | Service | Valeur |
|---|---|---|
| `DATABASE_URL` | api | URI Supabase (étape 1) |
| `APP_PASSWORD` | api | mot de passe de l'application |
| `INTERNAL_API_KEY` | api **et** app | la clé de l'étape 2, identique |
| `OPENAI_API_KEY` | api | clé OpenAI |
| `SEARCH_API_KEY` | api | clé Tavily (ou vide) |
| `BACKEND_URL` | app | URL publique de l'api, p. ex. `https://pantalelle-api.onrender.com` |

   `BACKEND_URL` n'est connue qu'après la création : si Render a ajouté un suffixe au nom, corrigez la valeur dans *app > Environment* puis relancez le déploiement de `pantalelle-app`.
3. Attendez les deux déploiements. Dans les logs de `pantalelle-api` vous devez voir `Running upgrade` (migrations) puis `Uvicorn running`.

## 4. Vérifications (dans cet ordre)

- [ ] `https://<api>.onrender.com/api/health` répond `{"status":"ok",…}` (c'est la seule route publique).
- [ ] `https://<api>.onrender.com/api/documents` répond **403** (la clé interne est bien exigée).
- [ ] `https://<app>.onrender.com` redirige vers `/login`, la connexion avec `APP_PASSWORD` fonctionne.
- [ ] Page *Documents* : ajoutez un petit fichier texte (vérifie la base, les migrations et la clé OpenAI).
- [ ] Chat : « Que sais-tu de Pantalelle ? » cite ce fichier.
- [ ] Une recherche d'entreprise répond avec des sources (vérifie Tavily).
- [ ] Sur Supabase, *Table Editor* montre `documents`, `chunks`, `alembic_version`.

## 5. Si ça ne marche pas

| Symptôme | Cause probable |
|---|---|
| L'api s'arrête avec `Refusing to start in production: …` | une variable manque ou est trop courte (le message dit laquelle) |
| La page s'ouvre mais tout renvoie 502 | `BACKEND_URL` erronée, ou l'api se réveille (patientez ~1 min sur la formule gratuite) |
| Tout renvoie 403 depuis le site | `INTERNAL_API_KEY` différente entre les deux services |
| `could not connect to server` dans l'api | mauvaise `DATABASE_URL`, ou connexion directe au lieu du Session pooler |
| `OPENAI_API_KEY is not configured` | variable absente sur l'api |
| Connexion refusée en boucle (429) | trop d'essais ; attendez 5 minutes |

## 6. Bon à savoir

- **Formule gratuite** : chaque service s'endort après 15 min sans trafic (réveil d'environ 1 min), le disque est éphémère, et Render la déconseille pour la production. Pour un usage quotidien, passez les deux services en `starter` (champ `plan`, consultez la tarification actuelle sur render.com/pricing).
- **Coûts** : OpenAI (messages, embeddings, images éventuelles) et Tavily sont facturés à l'usage : fixez une limite de dépense mensuelle chez chacun. Supabase gratuit : 500 Mo (documents compris) et pas de sauvegarde automatique sur ce palier : faites un `pg_dump` régulier si les données comptent.
- **Sécurité** : cookie `httpOnly` + `Secure`, API docs désactivées, 5 essais de connexion par adresse IP, puis 30 échecs au total en 5 minutes. L'adresse IP vient de l'en-tête `X-Forwarded-For` posé par Render : je n'ai pas pu confirmer son format dans leur documentation, d'où la limite globale. Conséquence : une personne malveillante qui échoue 30 fois bloque temporairement la connexion (5 minutes).
- **Changer le mot de passe** : modifiez `APP_PASSWORD` sur l'api (les sessions déjà ouvertes restent valides jusqu'à 7 jours ; pour tout déconnecter, changez aussi `SECRET_KEY`).
- **Mises à jour** : un push sur `main` redéploie automatiquement. Les migrations s'appliquent au démarrage de l'api.
- **Domaine personnalisé** : *pantalelle-app > Settings > Custom Domains*.

## Tester les images en local

```bash
docker compose up --build        # base + backend + frontend (images de production)
```

Définissez `INTERNAL_API_KEY` dans `.env` pour reproduire la protection (même valeur utilisée par les deux services).
