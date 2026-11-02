# ATELIER — TMS pour commissionnaire de transport

Application de démonstration full-stack : HTML/CSS/JavaScript + FastAPI + SQLite.

## Lancer l'application

1. Installer Python 3.10 ou supérieur.
2. Ouvrir un terminal dans le dossier `atelier_tms`.
3. Installer les dépendances :

   ```bash
   python -m venv .venv
   # Windows : .venv\\Scripts\\activate
   # macOS/Linux : source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. Démarrer le serveur :

   ```bash
   uvicorn main:app --reload
   ```

5. Ouvrir http://127.0.0.1:8000
6. Documentation interactive de l'API : http://127.0.0.1:8000/docs

La base SQLite est créée automatiquement dans `data/atelier.db` avec des données fictives de démonstration au premier lancement.

## Fonctionnalités connectées

- Dashboard : KPI calculés depuis SQLite (commandes, activité, affectations, livraisons, incidents, transporteurs, facturation, coûts et marge brute estimée), répartition par statut et synthèse économique.
- Commandes : création, recherche, filtrage, modification du statut, historique des événements et export CSV.
- Appels d'offres : création et changement de statut.
- Affectation manuelle : comparaison des transporteurs disponibles et affectation à une commande.
- Transporteurs : ajout et gestion de la disponibilité.
- Suivi & incidents : déclaration, affichage et résolution d'incidents.
- Documents : import de fichiers (12 Mo max) associés à une commande et téléchargement.
- Paramètres : sauvegarde en base.

## Données de présentation

Toutes les sociétés, commandes, tarifs, coordonnées et statistiques préchargés sont fictifs. Les montants sont en dirhams marocains. La marge affichée est une simulation calculée comme facturation client moins coûts transporteurs connus ; elle ne représente pas une comptabilité certifiée.

## Réinitialiser la démonstration

Arrêter le serveur, supprimer `data/atelier.db`, puis relancer `uvicorn main:app --reload`. La base et les données de démonstration seront recréées automatiquement. Les documents importés se trouvent dans `uploads/`.

## Déploiement

Déployer sur un hébergeur compatible ASGI avec la commande `uvicorn main:app --host 0.0.0.0 --port $PORT`. Pour conserver les données SQLite et les documents après redéploiement, configurer un volume disque persistant et placer `data/` et `uploads/` sur ce volume. Pour un usage réel multi-utilisateur, prévoir authentification, rôles, sauvegardes, validation métier, journalisation et stockage objet des documents.
