# VSS — Bot Telegram de contact avec une équipe bénévole

**Un point de contact simple pour transmettre un message à une équipe bénévole de prévention et d’accompagnement face aux violences sexistes et sexuelles (VSS).**

Dans ce contexte, « VSS » signifie **violences sexistes et sexuelles**. Par extension, on parle parfois de « l’équipe VSS » pour désigner les bénévoles mobilisés autour de ces sujets. Le bot facilite la mise en relation : une personne écrit en privé, le message arrive dans le groupe de l’équipe, et les bénévoles peuvent reprendre contact avec elle via Telegram. Il ne se substitue pas à l’écoute et à l’accompagnement humains.

Le dispositif peut servir dans un cadre associatif, étudiant ou événementiel. Le périmètre de l’équipe, ses horaires, sa formation et ses procédures doivent être définis par l’organisation qui l’utilise ; le code n’atteste pas ces éléments.

**Auteur : Marc Saade.** Développé en Python avec `python-telegram-bot`.

## Parcours utilisateur

1. La personne ouvre la conversation privée et utilise `/start` ou `/help` pour lire le fonctionnement et les informations de confidentialité.
2. Elle indique sa localisation et décrit, à son rythme, ce qu’elle souhaite partager.
3. Le bot transmet le message à un groupe Telegram configuré, accompagné du nom et d’un lien vers le profil de l’expéditeur.
4. Une confirmation est envoyée uniquement après confirmation de la copie par Telegram.
5. Les bénévoles peuvent contacter la personne séparément via Telegram selon leur disponibilité.

Les textes d’accueil, de confidentialité et de confirmation sont disponibles en français et en anglais. Le français est utilisé si la langue du profil Telegram commence par `fr`, l’anglais sinon. Les messages sans `/start` sont également transmis : informer les utilisateurs du partage avec l’équipe dans le descriptif public du bot.

## Fonctionnalités

- Réception en conversation privée ; les messages de groupe ne sont pas relayés.
- Copie du message original : le texte et les légendes ne sont pas remplacés par l’en-tête d’identité.
- En-tête séparé avec référence technique, nom, lien de profil et rappel du partage de l’identité.
- Association du message copié à son en-tête par une réponse Telegram, y compris pour les longs textes.
- Photos, vidéos, documents et vocaux via la copie Telegram, lorsque ce type de message est copiable par l’API.
- Échappement HTML des noms et pseudonymes dans l’en-tête.
- Protection Telegram contre le transfert et l’enregistrement du message relayé ; cela n’empêche pas toutes les formes de capture ou de copie manuelle.
- Destination configurable : groupe, supergroupe ou sujet d’un forum.
- Limite configurable de messages par utilisateur sur une fenêtre glissante d’une minute, pour modérer les envois répétés.
- Suivi temporaire des étapes d’envoi pour éviter de recopier un message déjà confirmé lorsque le même événement est reçu de nouveau dans le processus.
- Reprise bornée sur une réponse explicite de limitation Telegram (`RetryAfter`).
- Gestion des échecs : aucune confirmation de succès si la transmission n’a pas pu être confirmée.
- Validation de la configuration et du type de groupe au démarrage.
- Chargement d’un fichier `.env` local ; les variables du serveur restent prioritaires.
- Tests automatisés hors ligne et workflow GitHub Actions pour Python 3.12 et 3.13.

## Confidentialité et rôle de l’équipe

Ce service **n’est pas anonyme** : les bénévoles reçoivent le message et l’identité Telegram associée. Le bot ne crée pas de base de données de signalements, ne télécharge pas les pièces jointes et n’inscrit pas le contenu des messages dans ses journaux applicatifs. Telegram et les membres du groupe peuvent conserver les échanges.

Le suivi de livraison et la limitation des envois conservent uniquement des identifiants et des horodatages en mémoire, avec des tailles bornées. Le suivi de livraison expire après une heure ; les compteurs expirent lors du prochain traitement après une minute d’inactivité. Tout est perdu au redémarrage. Ne pas activer de journalisation HTTP détaillée : les URL Telegram peuvent contenir le jeton du bot.

Restreindre l’accès au groupe aux membres concernés et convenir avec eux de règles de conservation et de traitement des messages. Le bot ne prend aucune décision sur un signalement et ne garantit ni permanence humaine, ni délai de réponse. Une confirmation de transmission ne signifie pas qu’un bénévole a lu le message. Ce n’est pas un service d’urgence.

## Installation locale — Linux / WSL

Prérequis : Python 3.12 ou 3.13.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Renseigner le fichier `.env` local avec le jeton délivré par BotFather et l’identifiant du groupe, puis lancer :

```bash
python bot.py
```

Ne jamais committer le fichier `.env`. Il est exclu par `.gitignore`.

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Renseigner .env avant de démarrer.
py bot.py
```

## Configuration

| Variable | Description | Valeur par défaut |
| --- | --- | --- |
| `BOT_TOKEN` | Jeton du bot fourni par BotFather | Obligatoire |
| `TARGET_CHAT_ID` | Identifiant numérique négatif du groupe destinataire | Obligatoire |
| `TARGET_THREAD_ID` | Identifiant positif du sujet, si le groupe utilise un forum | Vide |
| `MESSAGES_PER_MINUTE` | Maximum de nouveaux messages acceptés par utilisateur sur 60 secondes | `20` |

Le bot doit appartenir au groupe destinataire et disposer des permissions nécessaires pour envoyer les types de messages attendus. Si un sujet est configuré, il doit exister dans ce groupe. Le démarrage vérifie le type de groupe ; les permissions d’envoi et le sujet doivent aussi être vérifiés lors de la recette.

## Déploiement

Le `Procfile` définit un worker :

```text
worker: python bot.py
```

Installer les dépendances et renseigner les variables d’environnement dans le tableau de bord de l’hébergeur. Exécuter **une seule instance** du worker en long polling pour ce jeton. La réception continue dépend de l’hébergement et de la connexion à Telegram. Les messages en attente ne sont pas volontairement effacés au redémarrage (`drop_pending_updates=False`).

Les messages envoyés à l’utilisateur changent avec cette version : prévenir l’équipe avant de redémarrer un déploiement existant et utiliser un bot/groupe de test pour la recette.

## Vérification

```bash
python -m unittest discover -s tests -v
```

Les tests simulent Telegram : messages longs, conservation des légendes, échappement HTML, groupes ignorés, doublons, confirmation après envoi, erreurs et timeouts, reprises sur limitation Telegram, plafond d’envoi, français/anglais, configuration et expiration des caches. Aucun jeton réel ni signalement n’est nécessaire.

Avant utilisation réelle, vérifier avec un bot et un groupe de test : `/start`, `/privacy`, texte, photo avec légende, vocal, document, accès au profil et éventuel sujet de forum. Les tests automatiques ne constituent pas un essai en production.

## Comportement en cas d’incident

Les timeouts ne sont pas rejoués automatiquement : Telegram a peut-être déjà reçu le message et une nouvelle copie pourrait créer un doublon. L’utilisateur reçoit alors une réponse indiquant que la transmission n’est pas confirmée. Le suivi temporaire évite certains doublons, mais ne fournit pas une garantie « exactement une fois », notamment après redémarrage ou timeout ambigu.

Les pièces d’un album sont transmises individuellement. Les modifications ultérieures d’un message ne sont pas relayées. Certains types Telegram ne sont pas copiables ; un échec est alors signalé à l’utilisateur. Les réponses des bénévoles se font directement sur Telegram ; le bot ne crée ni messagerie bidirectionnelle ni suivi de dossier.

## Publication du code et identifiants

Les exemples de ce dépôt ne doivent contenir que des valeurs fictives. **Un ancien jeton Telegram figurait dans l’historique du README : il doit être révoqué via BotFather avant publication**, même si le README actuel ne le contient plus. Mettre ensuite à jour `BOT_TOKEN` sur l’hébergeur et redémarrer le worker. Ne pas réutiliser l’ancien jeton.

L’identifiant du groupe n’est pas un jeton d’authentification ; le conserver néanmoins hors des exemples publics. Les jetons GitHub utilisés pour pousser le dépôt sont distincts du jeton Telegram et ne doivent jamais être placés dans les fichiers du projet.

## Structure

| Fichier | Rôle |
| --- | --- |
| `bot.py` | Configuration, commandes, relais et gestion des erreurs |
| `tests/test_bot.py` | Tests unitaires et tests des handlers asynchrones |
| `.env.example` | Modèle de configuration sans identifiants réels |
| `requirements.txt` | Dépendances Python épinglées |
| `Procfile` | Commande du worker |
| `.github/workflows/tests.yml` | Tests automatiques GitHub Actions |

## English summary

A Python Telegram bot connecting people with a volunteer team supporting those affected by sexual and gender-based violence. Private messages are copied to a designated team group with sender contact information, preserving text and media captions. The implementation includes bilingual user messages, configurable per-user throttling, bounded in-memory delivery tracking, privacy-conscious application logs, environment-based configuration and offline tests. Human follow-up happens separately through Telegram.
