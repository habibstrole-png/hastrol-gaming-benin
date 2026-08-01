# Hastrol Gaming Benin

Site de tournois esport hebdomadaires (Call of Duty Mobile & PUBG Mobile) en Python/Flask.

## Fonctionnalités

- Page d'accueil avec les cartes des deux jeux (image + inscription)
- Formulaire d'inscription à un tournoi (pseudo, plateforme, ID en jeu, contact, ville)
- Liste des joueurs inscrits à la semaine en cours
- Classement hebdomadaire (points, victoires, éliminations) qui repart à zéro chaque semaine
- Espace organisateur protégé par mot de passe pour saisir les résultats après un match

## 1. Lancer le site en local

```bash
cd hastrol
python3 -m venv venv
source venv/bin/activate        # sous Windows : venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Ouvre ensuite http://127.0.0.1:5000 dans ton navigateur.

La base de données `hastrol.db` (SQLite) se crée automatiquement au premier lancement.

## 2. Espace organisateur

- URL : `/admin/connexion`
- Mot de passe par défaut : `hastrol2026` (à changer absolument, voir ci-dessous)

Depuis cet espace, tu choisis un joueur inscrit et tu ajoutes ses points/victoires/éliminations après chaque match. Le classement se met à jour automatiquement.

## 3. Changer le mot de passe admin et la clé secrète

Avant de mettre le site en ligne, définis ces variables d'environnement (ne laisse jamais les valeurs par défaut en production) :

```bash
export ADMIN_PASSWORD="ton-mot-de-passe-solide"
export SECRET_KEY="une-longue-chaine-aleatoire"
```

## 4. Mettre le site en ligne (nom de domaine + hébergement)

Ce dossier est un site Flask standard, déployable sur n'importe quel hébergeur Python. Options simples et peu coûteuses :

- **Render.com** (gratuit pour démarrer) : crée un "Web Service", connecte ton dépôt GitHub, commande de démarrage : `gunicorn app:app`
- **PythonAnywhere** : hébergement Python simple, bon pour un premier déploiement
- **Railway.app** : déploiement automatique depuis GitHub

Étapes générales :
1. Mets ce dossier dans un dépôt GitHub.
2. Crée un compte sur l'hébergeur choisi et connecte le dépôt.
3. Renseigne les variables d'environnement `ADMIN_PASSWORD` et `SECRET_KEY`.
4. Achète un nom de domaine (ex: hastrolgaming.bj ou .com) chez un registrar (Namecheap, OVH...) et pointe-le vers l'hébergeur.

⚠️ Important : SQLite fonctionne bien pour démarrer, mais si le site grossit (beaucoup d'inscriptions), il est préférable de migrer vers PostgreSQL (la plupart des hébergeurs comme Render l'offrent gratuitement).

## 5. Personnaliser

- Couleurs et style : `static/css/style.css`
- Illustrations des jeux : `static/img/codm.svg` et `static/img/pubg.svg` (images originales, sans logo officiel — tu peux les remplacer par tes propres visuels)
- Textes des pages : dossier `templates/`
