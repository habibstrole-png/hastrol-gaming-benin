"""
Compatibilité base de données : utilise PostgreSQL si la variable d'environnement
DATABASE_URL est présente (cas de Render en production), sinon utilise SQLite
en local pour un développement simple sans configuration.
"""

import os
import sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras

    IntegrityError = psycopg2.IntegrityError
else:
    IntegrityError = sqlite3.IntegrityError


class DBConnection:
    """Enveloppe une connexion SQLite ou PostgreSQL avec une interface commune."""

    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=()):
        cur = self.conn.cursor()
        if USE_POSTGRES:
            sql = sql.replace("?", "%s")
        cur.execute(sql, params)
        return cur

    def executescript(self, sql):
        cur = self.conn.cursor()
        cur.execute(sql)
        self.conn.commit()

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def connect():
    """Ouvre une nouvelle connexion (PostgreSQL ou SQLite selon l'environnement)."""
    if USE_POSTGRES:
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, "hastrol.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
    return DBConnection(conn)


def schema_equipes():
    if USE_POSTGRES:
        return """
        CREATE TABLE IF NOT EXISTS equipes (
            id SERIAL PRIMARY KEY,
            nom TEXT NOT NULL,
            jeu TEXT NOT NULL,
            semaine TEXT NOT NULL,
            date_creation TEXT NOT NULL,
            UNIQUE(nom, jeu, semaine)
        );
        """
    return """
    CREATE TABLE IF NOT EXISTS equipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        jeu TEXT NOT NULL,
        semaine TEXT NOT NULL,
        date_creation TEXT NOT NULL,
        UNIQUE(nom, jeu, semaine)
    );
    """


def schema_joueurs():
    if USE_POSTGRES:
        return """
        CREATE TABLE IF NOT EXISTS joueurs (
            id SERIAL PRIMARY KEY,
            equipe_id INTEGER NOT NULL REFERENCES equipes(id) ON DELETE CASCADE,
            pseudo TEXT NOT NULL,
            plateforme TEXT NOT NULL,
            id_jeu TEXT NOT NULL,
            contact TEXT NOT NULL,
            est_capitaine INTEGER NOT NULL DEFAULT 0,
            date_inscription TEXT NOT NULL,
            UNIQUE(pseudo, equipe_id)
        );
        """
    return """
    CREATE TABLE IF NOT EXISTS joueurs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipe_id INTEGER NOT NULL,
        pseudo TEXT NOT NULL,
        plateforme TEXT NOT NULL,
        id_jeu TEXT NOT NULL,
        contact TEXT NOT NULL,
        est_capitaine INTEGER NOT NULL DEFAULT 0,
        date_inscription TEXT NOT NULL,
        FOREIGN KEY (equipe_id) REFERENCES equipes(id) ON DELETE CASCADE,
        UNIQUE(pseudo, equipe_id)
    );
    """


def schema_resultats():
    if USE_POSTGRES:
        return """
        CREATE TABLE IF NOT EXISTS resultats (
            id SERIAL PRIMARY KEY,
            equipe_id INTEGER NOT NULL REFERENCES equipes(id) ON DELETE CASCADE,
            points INTEGER NOT NULL DEFAULT 0,
            victoires INTEGER NOT NULL DEFAULT 0,
            eliminations INTEGER NOT NULL DEFAULT 0
        );
        """
    return """
    CREATE TABLE IF NOT EXISTS resultats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipe_id INTEGER NOT NULL,
        points INTEGER NOT NULL DEFAULT 0,
        victoires INTEGER NOT NULL DEFAULT 0,
        eliminations INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (equipe_id) REFERENCES equipes(id) ON DELETE CASCADE
    );
    """


def colonne_existe(db, table, colonne):
    if USE_POSTGRES:
        cur = db.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table,),
        )
        colonnes = [row["column_name"] for row in cur.fetchall()]
    else:
        colonnes = [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
    return colonne in colonnes


def inserer_et_recuperer_id(db, sql, params):
    """Exécute un INSERT et retourne l'id généré, pour PostgreSQL ou SQLite."""
    if USE_POSTGRES:
        cur = db.execute(sql + " RETURNING id", params)
        row = cur.fetchone()
        db.commit()
        return row["id"]
    cur = db.execute(sql, params)
    db.commit()
    return cur.lastrowid
