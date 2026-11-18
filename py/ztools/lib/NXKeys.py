import os
import re
from binascii import hexlify as hx, unhexlify as uhx
from pathlib import Path
my_file = Path('keys.txt')
my_file2 = Path('ztools\\keys.txt')	

class Keys(dict):
	def __init__(self, keys_type):
		self.keys_type = keys_type
		is_key  = re.compile(r'''\s*([a-zA-Z0-9_]*)\s* # name
								=
								\s*([a-fA-F0-9]*)\s* # key''', re.X)
		external = os.environ.get('NSCB_STUDIO_KEYS_FILE') if keys_type == 'keys.txt' else None
		candidates = (Path(external),) if external else (my_file2, my_file, Path(__file__).with_name(keys_type))
		source = next((file for file in candidates if file.is_file()), None)
		if source is None:
			raise FileNotFoundError('NSCB : fichier de cles introuvable. Selectionnez-le dans les reglages de Studio.')
		try:
			with source.open(encoding='utf-8-sig') as f:
				iterator = (is_key.search(line) for line in f)
				super(Keys, self).__init__({r[1]: uhx(r[2]) for r in iterator if r is not None})
		except (OSError, ValueError):
			if not external:
				raise
			raise RuntimeError('NSCB : fichier de cles illisible ou mal forme.') from None

	def __getitem__(self, item):
		try:
			return dict.__getitem__(self, item)
		except KeyError:
			raise KeyError('Missing key %s in %s' % (item, self.keys_type))

class ProdKeys(Keys):
	def __init__(self):
		super(ProdKeys, self).__init__('keys.txt')
		if 'header_key' in self:
			self['nca_header_key'] = self.pop('header_key')

class DevKeys(Keys):
	def __init__(self):
		super(DevKeys, self).__init__('dev')

class TitleKeys(Keys):
	def __init__(self):
		super(TitleKeys, self).__init__('title')
		if 'header_key' in self:
			self['nca_header_key'] = self.pop('header_key')
