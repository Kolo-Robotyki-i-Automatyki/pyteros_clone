import json
import os
import sys


SETTINGS_DIR = os.path.expanduser('~/pyteros_settings')


class Settings:
	def __init__(self, name: str):
		if not os.path.exists(SETTINGS_DIR):
			os.makedirs(SETTINGS_DIR)

		self.filename = os.path.join(SETTINGS_DIR, name)
		if not os.path.exists(self.filename):
			with open(self.filename, 'a') as f:
				pass
			with open(self.filename, 'w') as f:
				f.write('{}')

		self.cache = {}
		with open(self.filename, 'r') as f:
			try:
				self.cache = json.load(f)
			except Exception as e:
				print(e)
				self.cache = {}

	def set(self, key, val):
		self.cache[key] = val
		with open(self.filename, 'w') as f:
			json.dump(self.cache, f)

	def get(self, key, default=None):
		return self.cache.get(key, default)
