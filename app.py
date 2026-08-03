"""
Hastrol Gaming Benin
---------------------
Site de tournois esport hebdomadaires (Call of Duty Mobile & PUBG Mobile).
Inscription par équipe : 5 joueurs par équipe pour CODM, 4 joueurs par équipe pour PUBG.

Lancer en local :
    pip install -r requirements.txt
    python app.py
Puis ouvrir http://127.0.0.1:5000
"""

import os
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, render_template, request, redirect,
                    url_for, flash, session, g)

import db_compat

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cle-secrete-a-changer-en-production")

# mot de passe simple pour l'espace admin (à changer en variable d'environnement en prod)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "hastrol2026")

GAMES = {
    "codm": "Call of Duty Mobile",
    "pubg": "PUBG Mobile",
}

# taille d'équipe obligatoire par jeu
TAILLE_EQUIPE = {
    "codm": 5,
    "pubg": 4,
}


# ---------------------------------------------------------------------------
# Base de données
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = db_compat.connect()
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = db_compat.connect()
    db.executescript(db_compat.schema_equipes())
    db.executescript(db_compat.schema_joueurs())
    db.executescript(db_compat.schema_resultats())
    # migration douce : ajoute la colonne si une base existante ne l'a pas encore
    if not db_compat.colonne_existe(db, "joueurs", "est_capitaine"):
        db.execute("ALTER TABLE joueurs ADD COLUMN est_capitaine INTEGER NOT NULL DEFAULT 0")
        db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Semaine de tournoi en cours (lundi -> dimanche)
# ---------------------------------------------------------------------------

def semaine_courante():
    today = date.today()
    year, week, _ = today.isocalendar()
    return f"{year}-S{week:02d}"


def bornes_semaine():
    today = date.today()
    lundi = today - timedelta(days=today.weekday())
    dimanche = lundi + timedelta(days=6)
    return lundi, dimanche


# ---------------------------------------------------------------------------
# Aides équipes
# ---------------------------------------------------------------------------

def equipes_avec_effectif(db, jeu, semaine):
    """Retourne toutes les équipes de la semaine avec leur nombre de joueurs."""
    return db.execute(
        """
        SELECT e.id, e.nom, COUNT(j.id) AS effectif
        FROM equipes e
        LEFT JOIN joueurs j ON j.equipe_id = e.id
        WHERE e.jeu = ? AND e.semaine = ?
        GROUP BY e.id
        ORDER BY e.nom
        """,
        (jeu, semaine),
    ).fetchall()


# ---------------------------------------------------------------------------
# Auth admin
# ---------------------------------------------------------------------------

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            flash("Connecte-toi à l'espace admin pour continuer.", "erreur")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Routes publiques
# ---------------------------------------------------------------------------

@app.route("/")
def accueil():
    db = get_db()
    semaine = semaine_courante()
    lundi, dimanche = bornes_semaine()
    stats = {}
    for code in GAMES:
        equipes = equipes_avec_effectif(db, code, semaine)
        capacite = TAILLE_EQUIPE[code]
        completes = sum(1 for e in equipes if e["effectif"] >= capacite)
        en_formation = len(equipes) - completes
        joueurs_total = sum(e["effectif"] for e in equipes)
        stats[code] = {
            "equipes": len(equipes),
            "completes": completes,
            "en_formation": en_formation,
            "joueurs": joueurs_total,
        }
    return render_template(
        "accueil.html",
        jeux=GAMES,
        taille_equipe=TAILLE_EQUIPE,
        stats=stats,
        semaine=semaine,
        lundi=lundi,
        dimanche=dimanche,
    )


@app.route("/inscription/<jeu>", methods=["GET", "POST"])
def inscription(jeu):
    if jeu not in GAMES:
        flash("Jeu introuvable.", "erreur")
        return redirect(url_for("accueil"))

    db = get_db()
    semaine = semaine_courante()
    capacite = TAILLE_EQUIPE[jeu]

    if request.method == "POST":
        action = request.form.get("action")
        pseudo = request.form.get("pseudo", "").strip()
        plateforme = request.form.get("plateforme", "").strip()
        id_jeu = request.form.get("id_jeu", "").strip()
        contact = request.form.get("contact", "").strip()

        erreurs = []
        if len(pseudo) < 2:
            erreurs.append("Le pseudo doit contenir au moins 2 caractères.")
        if not plateforme:
            erreurs.append("Choisis ta plateforme (Android, iOS...).")
        if len(id_jeu) < 3:
            erreurs.append("Indique ton identifiant en jeu (ID CODM / ID PUBG).")
        if len(contact) < 8:
            erreurs.append("Indique un numéro de téléphone ou un email valide.")

        equipe_id = None
        est_capitaine = 0

        if action == "creer":
            nom_equipe = request.form.get("nom_equipe", "").strip()
            if len(nom_equipe) < 2:
                erreurs.append("Choisis un nom d'équipe d'au moins 2 caractères.")
            if not erreurs:
                try:
                    equipe_id = db_compat.inserer_et_recuperer_id(
                        db,
                        "INSERT INTO equipes (nom, jeu, semaine, date_creation) VALUES (?, ?, ?, ?)",
                        (nom_equipe, jeu, semaine, datetime.now().strftime("%Y-%m-%d %H:%M")),
                    )
                    est_capitaine = 1
                except db_compat.IntegrityError:
                    db.rollback()
                    erreurs.append("Ce nom d'équipe est déjà pris cette semaine pour ce jeu.")

        elif action == "rejoindre":
            equipe_id_brut = request.form.get("equipe_id")
            if not equipe_id_brut:
                erreurs.append("Choisis une équipe à rejoindre.")
            else:
                try:
                    equipe_id = int(equipe_id_brut)
                except ValueError:
                    equipe_id = None
                    erreurs.append("Équipe invalide.")
            if equipe_id is not None:
                ligne = db.execute(
                    "SELECT COUNT(*) AS n FROM joueurs WHERE equipe_id = ?", (equipe_id,)
                ).fetchone()
                if ligne["n"] >= capacite:
                    erreurs.append("Cette équipe est déjà complète.")
        else:
            erreurs.append("Choisis de créer une équipe ou d'en rejoindre une.")

        if erreurs:
            for e in erreurs:
                flash(e, "erreur")
            equipes = equipes_avec_effectif(db, jeu, semaine)
            return render_template("inscription.html", jeu=jeu, nom_jeu=GAMES[jeu],
                                    capacite=capacite, equipes=equipes, form=request.form)

        try:
            db.execute(
                """INSERT INTO joueurs (equipe_id, pseudo, plateforme, id_jeu, contact, est_capitaine, date_inscription)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (equipe_id, pseudo, plateforme, id_jeu, contact, est_capitaine,
                 datetime.now().strftime("%Y-%m-%d %H:%M")),
            )
            db.commit()
        except db_compat.IntegrityError:
            db.rollback()
            flash("Ce pseudo est déjà inscrit dans cette équipe.", "erreur")
            equipes = equipes_avec_effectif(db, jeu, semaine)
            return render_template("inscription.html", jeu=jeu, nom_jeu=GAMES[jeu],
                                    capacite=capacite, equipes=equipes, form=request.form)

        return redirect(url_for("confirmation", jeu=jeu))

    equipes = equipes_avec_effectif(db, jeu, semaine)
    return render_template("inscription.html", jeu=jeu, nom_jeu=GAMES[jeu],
                            capacite=capacite, equipes=equipes, form={})


@app.route("/inscription/<jeu>/confirmation")
def confirmation(jeu):
    if jeu not in GAMES:
        return redirect(url_for("accueil"))
    return render_template("confirmation.html", jeu=jeu, nom_jeu=GAMES[jeu])


@app.route("/classement")
def classement():
    db = get_db()
    jeu = request.args.get("jeu", "codm")
    if jeu not in GAMES:
        jeu = "codm"
    semaine = request.args.get("semaine", semaine_courante())

    equipes = db.execute(
        """
        SELECT e.id, e.nom,
               COALESCE(SUM(r.points), 0) AS points,
               COALESCE(SUM(r.victoires), 0) AS victoires,
               COALESCE(SUM(r.eliminations), 0) AS eliminations
        FROM equipes e
        LEFT JOIN resultats r ON r.equipe_id = e.id
        WHERE e.jeu = ? AND e.semaine = ?
        GROUP BY e.id
        ORDER BY points DESC, victoires DESC, eliminations DESC
        """,
        (jeu, semaine),
    ).fetchall()

    # membres de chaque équipe (pour affichage)
    membres = {}
    for eq in equipes:
        rows = db.execute(
            "SELECT pseudo, est_capitaine FROM joueurs WHERE equipe_id = ? ORDER BY est_capitaine DESC, date_inscription ASC",
            (eq["id"],),
        ).fetchall()
        membres[eq["id"]] = [
            (r["pseudo"] + " (capitaine)" if r["est_capitaine"] else r["pseudo"]) for r in rows
        ]

    semaines = [row["semaine"] for row in db.execute(
        "SELECT DISTINCT semaine FROM equipes WHERE jeu = ? ORDER BY semaine DESC", (jeu,)
    ).fetchall()]
    if semaine not in semaines:
        semaines.insert(0, semaine)

    return render_template(
        "classement.html",
        jeux=GAMES,
        jeu=jeu,
        nom_jeu=GAMES[jeu],
        equipes=equipes,
        membres=membres,
        semaine=semaine,
        semaines=semaines,
    )


@app.route("/joueurs")
def liste_joueurs():
    db = get_db()
    jeu = request.args.get("jeu", "codm")
    if jeu not in GAMES:
        jeu = "codm"
    semaine = semaine_courante()
    capacite = TAILLE_EQUIPE[jeu]

    equipes = db.execute(
        "SELECT id, nom, date_creation FROM equipes WHERE jeu = ? AND semaine = ? ORDER BY date_creation ASC",
        (jeu, semaine),
    ).fetchall()

    equipes_detail = []
    for eq in equipes:
        joueurs = db.execute(
            "SELECT pseudo, plateforme, est_capitaine, date_inscription FROM joueurs "
            "WHERE equipe_id = ? ORDER BY est_capitaine DESC, date_inscription ASC",
            (eq["id"],),
        ).fetchall()
        equipes_detail.append({"equipe": eq, "joueurs": joueurs, "complete": len(joueurs) >= capacite})

    return render_template("joueurs.html", jeux=GAMES, jeu=jeu, nom_jeu=GAMES[jeu],
                            equipes_detail=equipes_detail, capacite=capacite, semaine=semaine)


# ---------------------------------------------------------------------------
# Espace admin
# ---------------------------------------------------------------------------

@app.route("/admin/connexion", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("mot_de_passe") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_resultats"))
        flash("Mot de passe incorrect.", "erreur")
    return render_template("admin_login.html")


@app.route("/admin/deconnexion")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("accueil"))


@app.route("/admin/resultats", methods=["GET", "POST"])
@admin_required
def admin_resultats():
    db = get_db()
    jeu = request.args.get("jeu", "codm")
    if jeu not in GAMES:
        jeu = "codm"
    semaine = semaine_courante()

    if request.method == "POST":
        equipe_id_brut = request.form.get("equipe_id")
        try:
            equipe_id = int(equipe_id_brut)
        except (TypeError, ValueError):
            flash("Équipe invalide.", "erreur")
            return redirect(url_for("admin_resultats", jeu=jeu))
        points = int(request.form.get("points") or 0)
        victoires = int(request.form.get("victoires") or 0)
        eliminations = int(request.form.get("eliminations") or 0)
        db.execute(
            "INSERT INTO resultats (equipe_id, points, victoires, eliminations) VALUES (?, ?, ?, ?)",
            (equipe_id, points, victoires, eliminations),
        )
        db.commit()
        flash("Résultat ajouté au classement.", "succes")
        return redirect(url_for("admin_resultats", jeu=jeu))

    equipes = db.execute(
        "SELECT id, nom FROM equipes WHERE jeu = ? AND semaine = ? ORDER BY nom",
        (jeu, semaine),
    ).fetchall()
    return render_template("admin_resultats.html", jeux=GAMES, jeu=jeu, nom_jeu=GAMES[jeu],
                            equipes=equipes, semaine=semaine)


@app.route("/admin/joueurs", methods=["GET"])
@admin_required
def admin_joueurs():
    db = get_db()
    jeu = request.args.get("jeu", "codm")
    if jeu not in GAMES:
        jeu = "codm"
    semaine = semaine_courante()
    capacite = TAILLE_EQUIPE[jeu]

    equipes = db.execute(
        "SELECT id, nom FROM equipes WHERE jeu = ? AND semaine = ? ORDER BY nom",
        (jeu, semaine),
    ).fetchall()

    equipes_detail = []
    for eq in equipes:
        joueurs = db.execute(
            "SELECT id, pseudo, plateforme, id_jeu, contact, est_capitaine FROM joueurs "
            "WHERE equipe_id = ? ORDER BY est_capitaine DESC, date_inscription ASC",
            (eq["id"],),
        ).fetchall()
        equipes_detail.append({"equipe": eq, "joueurs": joueurs, "complete": len(joueurs) >= capacite})

    return render_template("admin_joueurs.html", jeux=GAMES, jeu=jeu, nom_jeu=GAMES[jeu],
                            equipes_detail=equipes_detail, capacite=capacite, semaine=semaine)


@app.route("/admin/joueurs/ajouter", methods=["POST"])
@admin_required
def admin_ajouter_joueur():
    db = get_db()
    jeu = request.form.get("jeu", "codm")
    equipe_id = request.form.get("equipe_id")
    pseudo = request.form.get("pseudo", "").strip()
    plateforme = request.form.get("plateforme", "Android").strip() or "Android"
    id_jeu = request.form.get("id_jeu", "").strip() or "N/A"
    contact = request.form.get("contact", "").strip() or "N/A"

    if not equipe_id or len(pseudo) < 2:
        flash("Choisis une équipe et un pseudo valide.", "erreur")
        return redirect(url_for("admin_joueurs", jeu=jeu))

    try:
        equipe_id = int(equipe_id)
    except ValueError:
        flash("Équipe invalide.", "erreur")
        return redirect(url_for("admin_joueurs", jeu=jeu))

    try:
        db.execute(
            """INSERT INTO joueurs (equipe_id, pseudo, plateforme, id_jeu, contact, est_capitaine, date_inscription)
               VALUES (?, ?, ?, ?, ?, 0, ?)""",
            (equipe_id, pseudo, plateforme, id_jeu, contact, datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        db.commit()
        flash(f"{pseudo} a été ajouté à l'équipe.", "succes")
    except db_compat.IntegrityError:
        db.rollback()
        flash("Ce pseudo existe déjà dans cette équipe.", "erreur")

    return redirect(url_for("admin_joueurs", jeu=jeu))


@app.route("/admin/joueurs/supprimer/<int:joueur_id>", methods=["POST"])
@admin_required
def admin_supprimer_joueur(joueur_id):
    db = get_db()
    jeu = request.form.get("jeu", "codm")

    joueur = db.execute(
        "SELECT j.id, j.equipe_id, j.pseudo, j.est_capitaine FROM joueurs j WHERE j.id = ?",
        (joueur_id,),
    ).fetchone()

    if joueur is None:
        flash("Joueur introuvable.", "erreur")
        return redirect(url_for("admin_joueurs", jeu=jeu))

    equipe_id = joueur["equipe_id"]
    db.execute("DELETE FROM joueurs WHERE id = ?", (joueur_id,))
    db.commit()
    flash(f"{joueur['pseudo']} a été retiré de l'équipe.", "succes")

    # si le capitaine est supprimé, le joueur restant le plus ancien devient capitaine
    if joueur["est_capitaine"]:
        prochain = db.execute(
            "SELECT id FROM joueurs WHERE equipe_id = ? ORDER BY date_inscription ASC LIMIT 1",
            (equipe_id,),
        ).fetchone()
        if prochain:
            db.execute("UPDATE joueurs SET est_capitaine = 1 WHERE id = ?", (prochain["id"],))
            db.commit()

    return redirect(url_for("admin_joueurs", jeu=jeu))


@app.route("/admin/equipes/supprimer/<int:equipe_id>", methods=["POST"])
@admin_required
def admin_supprimer_equipe(equipe_id):
    db = get_db()
    jeu = request.form.get("jeu", "codm")
    db.execute("DELETE FROM equipes WHERE id = ?", (equipe_id,))
    db.commit()
    flash("Équipe supprimée.", "succes")
    return redirect(url_for("admin_joueurs", jeu=jeu))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
else:
    init_db()
