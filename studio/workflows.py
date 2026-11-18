"""Guided workflows and Squirrel argument lists for NSCB Studio."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory


@dataclass(frozen=True)
class Workflow:
    id: str
    title: str
    category: str
    description: str
    extensions: tuple[str, ...]
    output: bool = False
    mode: str = 'each'
    choices: tuple[str, ...] = ()
    caution: str = ''


_PACKAGES = ('.nsp', '.xci', '.nsz', '.xcz')
_REPORTS = ('.nsp', '.xci', '.nsx', '.nsz', '.xcz')
_BUFFER = ('-b', '65536')
_FAT = ('-fat', 'exfat', '-fx', 'files')
_REPACK = (*_BUFFER, '-pv', 'false', '-kp', 'false', '--RSVcap', '268435656',
           *_FAT, '-ND', 'true')  # py/zconfig/NSCB_options.cmd

WORKFLOWS = [
    Workflow('contents', 'Lister les contenus', 'Inspection', 'Lister les contenus par identifiant de titre de base.', _REPORTS),
    Workflow('firmware', 'Firmware requis', 'Inspection', 'Afficher la version système requise.', _REPORTS),
    Workflow('verify', 'Vérifier un fichier', 'Inspection', 'Contrôler l’intégrité du fichier.', _REPORTS,
             choices=('lv1', 'lv2', 'lv3')),
    Workflow('convert', 'Convertir', 'Assemblage', 'Convertir chaque fichier en NSP, en XCI ou dans les deux formats.',
             _PACKAGES, output=True, choices=('nsp', 'xci', 'both')),
    Workflow('merge', 'Fusionner', 'Assemblage', 'Regrouper tous les fichiers sélectionnés dans un même ensemble.',
             _PACKAGES, output=True, mode='group', choices=('nsp', 'xci', 'both', 'cnsp', 'cboth')),
    Workflow('split', 'Séparer les contenus', 'Assemblage', 'Séparer les contenus par identifiant de titre.',
             _PACKAGES, output=True, choices=('nsp', 'xci', 'both')),
    Workflow('extract', 'Extraire', 'Fichiers', 'Extraire les fichiers lisibles ou utiliser l’extraction brute.',
             _REPORTS, output=True, choices=('standard', 'raw')),
    Workflow('trim', 'Ajuster la taille d’un XCI', 'Fichiers', 'Réduire la taille, retirer la partition de mise à jour ou rétablir le remplissage.',
             ('.xci',), output=True, choices=('-xci_tr', '-xci_st', '-xci_untr'),
             caution='Le mode Supertrim retire la partition de mise à jour du fichier produit.'),
    Workflow('compress', 'Compresser', 'Compression', 'Compresser un NSP en NSZ ou un XCI en XCZ.',
             ('.nsp', '.xci'), output=True,
             choices=('17', *(str(i) for i in range(1, 23) if i != 17))),
    Workflow('decompress', 'Décompresser', 'Compression', 'Décompresser un NSZ en NSP ou un XCZ en XCI.',
             ('.nsz', '.xcz'), output=True),
    Workflow('join', 'Joindre des fragments', 'Fichiers', 'Sélectionner le premier fragment et laisser les suivants dans le même dossier.',
             ('.ns0', '.xc0', '.00'), output=True, caution='Ne sélectionne que le premier fragment de chaque ensemble.'),
    Workflow('rename', 'Renommer par métadonnées', 'Fichiers', 'Renommer sur place chaque fichier sélectionné.',
             _REPORTS, choices=('skip_corr_tid', 'skip_if_tid', 'force'),
             caution='Cette opération change le nom des fichiers d’origine.'),
    Workflow('restore', 'Restaurer un fichier', 'Fichiers', 'Restaurer les fichiers NSP ou XCI modifiés que le moteur sait vérifier.',
             ('.nsp', '.xci'), output=True, caution='La restauration des fichiers multicontenus n’est pas prise en charge.'),
]

# py/ztools/info.bat:150,197 uses direct arguments, which prompt at the console.
# Squirrel's -tfile branches avoid prompts; NSCB.bat:1464 uses list mode for verification.
# List-based options with nargs='+' require the empty argv token shown in the batches.
_ARGUMENTS = {
    'contents': ('{out}', '{list}', '--ADVcontentlist', '{file}'),
    'firmware': ('{out}', '--translate', 'FALSE', '{list}', '--fw_req', '{file}'),
    'verify': (*_BUFFER, '{out}', '-vt', '{choice}', '{list}', '-v', '{file}'),
    # py/NSCB.bat:590–592, 2599–2601, 1539–1542, 1372
    'convert': (*_REPACK, '{out}', '-t', '{choice}', '-dc', '{file}'),
    # NSCB.bat:2124–2140: direct multi reads the whole manifest; dual exports are separate jobs.
    'merge': (*_REPACK, '-t', '{choice}', '{out}', '{list}', '-roma', 'TRUE', '-dmul', 'calculate'),
    'split': (*_BUFFER, '{out}', *_FAT, '-t', '{choice}', '-dspl', '{file}', '{list}'),
    'trim': (*_BUFFER, '{out}', '{list}', '{choice}', '{file}'),
    'rename': ('-renf', 'single', '{list}', '-t', *(ext[1:] for ext in _REPORTS),
               '-renm', '{choice}', '-nover', 'false', '-oaid', 'false', '-addl', 'false',
               '-roma', 'TRUE', '-dlcrn', 'false', '-threads', '1'),
    # py/ztools/ADV.bat:220,239; ZSTD.bat:333,438; JOINER.bat:208; RST.bat:223
    'extract': (*_BUFFER, '{out}', '{list}', '{extract_flag}', ''),
    'compress': (*_BUFFER, '{out}', '{list}', '--compress', '{choice}', '--threads', '0',
                 '--nodelta', 'true', '--fexport', 'xcz'),
    'decompress': ('{out}', '{list}', '--decompress', 'auto'),
    'join': (*_BUFFER, '{out}', '{list}', '--joinfile', ''),
    'restore': (*_BUFFER, '{out}', '{list}', '--restore', ''),
}


@lru_cache(maxsize=1)
def _list_directory() -> TemporaryDirectory:
    return TemporaryDirectory(prefix='nscb-studio-')


def _file_list(files: list[Path]) -> str:
    # Use absolute paths because Squirrel runs from its own working directory.
    # Keep lists alive for queued jobs without reusing a previous run's list.
    data = ''.join(f'{path.absolute()}\n' for path in files).encode('utf-8')
    with NamedTemporaryFile(dir=_list_directory().name, suffix='.txt', delete=False) as target:
        target.write(data)
        return target.name


def build_jobs(workflow: Workflow, files: list[Path], output: Path | None,
               choice: str) -> list[list[str]]:
    """Return Squirrel argv vectors, without the interpreter or script path."""
    if not files:
        raise ValueError('Select at least one input file.')
    if workflow.output and output is None:
        raise ValueError('Select an output directory.')
    if not choice and workflow.choices:
        choice = workflow.choices[0]
    if choice and choice not in workflow.choices:
        raise ValueError(f'Invalid choice for {workflow.title}: {choice}')
    for path in files:
        suffix = '.00' if path.name == '00' else path.suffix if path.suffix != '.00' else ''
        if workflow.extensions and suffix not in workflow.extensions:
            raise ValueError(f'Unsupported input for {workflow.title}: {path}')
        if '\n' in str(path) or '\r' in str(path):
            raise ValueError(f'Input path cannot contain a line break: {path!r}')

    template = _ARGUMENTS.get(workflow.id)
    if template is None:
        raise ValueError(f'Unknown workflow: {workflow.id}')
    groups = [files] if workflow.mode == 'group' else [[path] for path in files]
    if workflow.id == 'merge' and choice == 'both':
        targets = ('nsp', 'xci')
    elif workflow.id == 'merge' and choice == 'cboth':
        targets = ('xci', 'cnsp')
    else:
        targets = (choice,)

    destination = () if output is None else ('-o', str(output.absolute()))
    jobs = []
    for group in groups:
        values = {
            '{out}': destination,
            '{list}': ('-tfile', _file_list(group)) if '{list}' in template else (),
            '{file}': (str(group[0].absolute()),),
            '{extract_flag}': ('-raw_x' if choice == 'raw' else '-x',),
        }
        for target in targets:
            values['{choice}'] = (target,)
            jobs.append([arg for token in template for arg in values.get(token, (token,))])
    return jobs
