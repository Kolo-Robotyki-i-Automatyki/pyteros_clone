import json
import os
import sys


USER_SETTINGS_DIR = 'config'
DEFAULT_SETTINGS_DIR = os.path.join(USER_SETTINGS_DIR, 'default')


class Settings:
	def __init__(self, name: str):
		self.config_default = os.path.join(DEFAULT_SETTINGS_DIR, name)
		self.config_user = os.path.join(USER_SETTINGS_DIR, name)

		self.cache = None

		if os.path.exists(self.config_user):
			try:
				with open(self.config_user, 'r') as f:
					self.cache = json.load(f)
			except Exception as e:
				print('loading settings for "{}": {}'.format(name, e))

		if self.cache is None:
			if os.path.exists(self.config_default):
				with open(self.config_default, 'r') as f:
					self.cache = json.load(f)
			else:
				self.cache = {}

			with open(self.config_user, 'a') as f:
				pass
			self.save()

	def save(self):		
		with open(self.config_user, 'w') as f:
			json.dump(self.cache, f, indent=4)

	def set(self, key, val, save=True):
		self.cache[key] = val
		if save:
			self.save()

	def get(self, key, default=None):
		return self.cache.get(key, default)
