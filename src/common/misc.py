import base64
import importlib
import json
import numpy as np
import threading
import time
import traceback
import typing


def create_obj_from_path(class_path: str, *args, **kwargs):
    module_name, class_name = class_path.rsplit('.', 1)
    imported_module = importlib.import_module(module_name)
    class_obj = getattr(imported_module, class_name)
    return class_obj(*args, **kwargs)


def clamp(val, min_val, max_val):
	if type(val) != type(min_val):
		raise TypeError('min_val has type {} ({} expected)'.format(type(min_val), type(val)))
	if type(val) != type(max_val):
		raise TypeError('max_val has type {} ({} expected)'.format(type(max_val), type(val)))
	return min(max_val, max(min_val, val))


def linear_interpolation(min_val: float, max_val: float, alpha: float):
	return min_val + (max_val - min_val) * alpha


def unique_id(obj):
	return '{}_{}'.format(id(obj), time.time())


# Support for decoding/encoding numpy arrays
class NumpyArrayEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            data = base64.b64encode(obj.tostring()).decode('ascii')
            return dict(dtype=object.dtype.str, shape=obj.shape, data=data)
        else:
	        return json.JSONEncoder.default(self, obj)

class NumpyArrayDecoder(json.JSONDecoder):
	def __init__(self, *args, **kwargs):
		super().__init__(object_hook=self.object_hook, *args, **kwargs)

	def object_hook(self, obj):
		try:
			dtype = obj['dtype']
			shape = obj['shape']
			data = obj['data']

			array = np.frombuffer(base64.standard_b64decode(data), dtype=dtype)
			array.reshape(shape)
			return array
		except:
			return obj


class DaemonController:
	def __init__(self):
		self.continue_running = True
		self.thread = None

	def stop(self):
		self.continue_running = False
		try:
			self.thread.join()
		except:
			pass

	def should_run(self):
		return self.continue_running

def run_daemon_in_loop(worker: typing.Callable, delay: float, args: typing.Tuple = (), kwargs: typing.Dict = {}):
	controller = DaemonController()

	def wrapper():
		while controller.should_run():
			try:
				worker(*args, **kwargs)
			except Exception as e:
				traceback.print_exc()
				print('Uncaught exception in {}()'.format(worker.__name__))
			time.sleep(delay)

	controller.thread = threading.Thread(target=wrapper, daemon=True)
	controller.thread.start()

	return controller
