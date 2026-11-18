"""Replace a game patch with Squirrel, then verify the staged XCI before publishing."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

if __name__ != '__main__':
    from studio.runner import execute


@dataclass(frozen=True)
class Title:
    id: str
    kind: str
    version: int
    files: frozenset[str]


def _index(titles):
    result = {}
    for title in titles:
        if title.id in result:
            raise ValueError('Plusieurs entrées portent le même identifiant de titre.')
        result[title.id] = title
    return result


def expected_titles(original, update):
    previous = _index(original)
    games = [t for t in previous.values() if t.kind == 'BASE']
    if len(games) != 1:
        raise ValueError('Le XCI doit contenir exactement un jeu de base.')
    if len(update) != 1 or update[0].kind != 'UPDATE':
        raise ValueError('Le NSP doit contenir uniquement une mise à jour de jeu.')
    patch = update[0]
    # Switch title IDs: the patch ID is the application ID + 0x800.
    if int(patch.id, 16) != int(games[0].id, 16) + 0x800:
        raise ValueError('Cette mise à jour ne correspond pas au jeu de base du XCI.')
    old = previous.get(patch.id)
    if old and (old.kind != 'UPDATE' or patch.version <= old.version):
        raise ValueError('La mise à jour sélectionnée doit être plus récente que celle du XCI.')
    previous[patch.id] = patch
    return previous


def validate_result(expected, actual):
    found = _index(actual)
    if found != expected:
        raise ValueError('Le XCI reconstruit ne contient pas exactement le jeu, les DLC et la mise à jour attendus. Aucun fichier final n’a été créé.')


def inspect_titles(path, engine, binary, env, stop, temp):
    result = temp / 'inspection.json'
    result.unlink(missing_ok=True)
    code = execute([binary, '-u', str(Path(__file__).resolve())],
                   [[str(engine.parent), str(path), str(result)]], engine.parent, env, stop, lambda _: None)
    if code is None:
        return None
    if code == 3:
        raise ValueError('Clés absentes, incomplètes ou incompatibles. Sélectionne un fichier de clés compatible dans Réglages.')
    if code or not result.is_file():
        raise ValueError(f'Impossible de lire toutes les métadonnées de « {path.name} ». Vérifie le fichier et la compatibilité des clés.')
    return [Title(title, kind, version, frozenset(files)) for title, kind, version, files in
            json.loads(result.read_text(encoding='utf-8'))]


def replace_update(base, update, destination, engine, binary, env, stop, emit):
    base, update, destination = (p.resolve() for p in (base, update, destination))
    if (base.suffix, update.suffix) != ('.xci', '.nsp') or not base.is_file() or not update.is_file():
        raise ValueError('Sélectionne un XCI d’origine et un NSP de mise à jour existants (extensions .xci et .nsp).')
    if destination.suffix.lower() != '.xci' or destination.exists():
        raise ValueError('Choisis un nouveau nom .xci : aucun fichier existant ne sera remplacé.')
    if not destination.parent.is_dir():
        raise ValueError('Le dossier de destination n’existe pas.')
    if stop.is_set():
        return False
    with TemporaryDirectory(prefix='.nscb-update-', dir=destination.parent) as directory:
        temp = Path(directory)
        emit('Lecture du XCI d’origine et du NSP…\n')
        original = inspect_titles(base, engine, binary, env, stop, temp)
        if original is None or stop.is_set():
            return False
        patch = inspect_titles(update, engine, binary, env, stop, temp)
        if patch is None or stop.is_set():
            return False
        expected = expected_titles(original, patch)
        emit(f'Mise à jour v{patch[0].version} · {sum(t.kind == "DLC" for t in expected.values())} DLC à conserver.\n')
        if shutil.disk_usage(destination.parent).free < base.stat().st_size + update.stat().st_size:
            raise ValueError('Espace libre insuffisant pour reconstruire le XCI. Prévois au moins la taille des deux fichiers sources.')
        manifest = temp / 'sources.txt'
        manifest.write_text(f'{base}\n{update}\n', encoding='utf-8')
        args = ['-o', str(temp), '-t', 'xci', '-ND', 'false', '-pv', 'false', '-kp', 'false',
                '-tfile', str(manifest), '-dmul', 'calculate']
        emit('Reconstruction du XCI dans un dossier temporaire…\n')
        # The legacy engine can print sensitive material. Only emit Studio messages.
        code = execute([binary, '-u', str(engine)], [args], engine.parent, env, stop, lambda _: None)
        if code is None or stop.is_set():
            return False
        results = list(temp.glob('*.xci'))
        if code or len(results) != 1:
            raise ValueError('Squirrel n’a pas produit un XCI unique. Aucun fichier final n’a été créé.')
        emit('Vérification du jeu, des DLC et de la version du patch…\n')
        actual = inspect_titles(results[0], engine, binary, env, stop, temp)
        if actual is None or stop.is_set():
            return False
        validate_result(expected, actual)
        # Windows rename refuses to replace an existing destination. POSIX link
        # gives the same guarantee, and the temporary directory is on the same volume.
        if os.name == 'nt':
            results[0].rename(destination)
        else:
            os.link(results[0], destination)
        emit(f'XCI vérifié : {destination}\n')
        return True


def _probe(engine_dir, path, result):
    os.chdir(engine_dir)
    sys.path[:0] = [str(engine_dir / 'lib'), str(engine_dir)]
    try:
        import sq_settings
        sq_settings.set_prod_environment()
        import Keys
        if not Keys.keys:
            return 3
    except Exception:
        return 3
    try:
        import Fs
        # Xci's constructor takes only a path and opens it in rb by default.
        source = Fs.Xci(str(path)) if path.suffix == '.xci' else Fs.Nsp(str(path), 'rb')
        try:
            files = source
            if path.suffix == '.xci':
                files = next(part for part in source.hfs0 if str(part._path) == 'secure')
            inventory = {str(item._path): item.size for item in files if str(item._path).endswith('.nca')}
            metadata = {name for name in inventory if name.endswith('.cnmt.nca')}
            titles = []
            seen = set()
            for _, title, _, _, records, kind, version in source.get_content(False, False, True):
                names = {name: size for name, size in records if name.endswith('.nca')}
                metas = metadata & names.keys()
                if len(metas) != 1 or seen & metas or any(inventory.get(name) != size for name, size in names.items()):
                    return 4
                seen.update(metas)
                titles.append([title, kind, int(version), sorted(names)])
            if not titles or seen != metadata:
                return 4
            result.write_text(json.dumps(titles), encoding='utf-8')
        finally:
            source.close()
    except Exception:
        return 4
    return 0


if __name__ == '__main__':
    raise SystemExit(_probe(*map(Path, sys.argv[1:])))
