# NSCB Studio

Interface Windows en Python/Tk pour le moteur Squirrel de NSC_Builder. Les traitements restent ceux du projet d’origine ; Studio ne réimplémente pas les formats de fichiers.

## Démarrage sous Windows

Si `.venv` est déjà installé, double-clique sur **NSCB Studio.cmd** à la racine du projet. Sinon, depuis la racine, avec [uv](https://docs.astral.sh/uv/getting-started/installation/) :

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -r studio/requirements.txt
.venv/Scripts/python.exe -m studio.app
```

Cette dernière commande permet aussi de voir une éventuelle erreur de démarrage dans le terminal. Tests : ` .venv/Scripts/python.exe -m unittest discover -s studio -v`.

## Utilisation

- **Opérations** : sélectionne un traitement, ajoute les fichiers, puis choisis le dossier de sortie et les options affichées. Certaines opérations modifient les originaux (par exemple le renommage) : travaille d’abord sur des copies.
- **Remplacer une mise à jour** : sélectionne le XCI d’origine, un NSP contenant uniquement un patch plus récent du même jeu et un nouveau nom de fichier XCI. Studio lit les métadonnées avec les clés locales, reconstruit dans un dossier temporaire puis vérifie le jeu, la version du patch, les DLC et leurs entrées NCA avant de publier le fichier. Les fichiers existants ne sont pas écrasés. Prévois sur le lecteur de destination un espace libre d’au moins la taille combinée des deux sources.
- **Catalogue Squirrel** : cherche un argument ou sa description, saisis une valeur par ligne, ajoute-le à la commande, et associe les options nécessaires. Le catalogue est extrait du code d’origine sans importer le moteur. Les descriptions amont restent en anglais. Le catalogue ne vérifie pas la compatibilité entre tous les arguments. Privilégie les opérations guidées pour les commandes interactives.
- **Réglages & modes classiques** : sélectionne un fichier de clés local sans le copier. Le chemin est transmis aux processus NSCB démarrés par Studio ; la sélection n’est pas mémorisée. Le menu Batch, File Info dans le navigateur et le serveur restent des interfaces d’origine. Les services distants, Chromium/Chrome, DBI/MTP, et certains sous-outils peuvent nécessiter les réglages ou fichiers supplémentaires décrits dans le README amont. Aucune connexion de compte ni opération sur une console n’est effectuée par Studio au démarrage.
- **Journal** : la sortie de Squirrel s’affiche pendant le traitement. Le moteur ignore parfois des erreurs et quitte avec le code 0 ; consulte le journal et vérifie les fichiers produits. L’arrêt interrompt le moteur direct et peut laisser des fichiers incomplets.

Studio ne remplace pas intégralement l’interface des modes classiques et ne garantit pas tous les scénarios d’origine.
