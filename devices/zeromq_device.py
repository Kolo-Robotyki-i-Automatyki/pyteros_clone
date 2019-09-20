'''
This code was originally written by Tomasz Kazimierczuk for LUMS - Laboratory
of Ultrafast MagnetoSpectroscopy at Faculty of Physics, University of Warsaw

'''

import enum
import sys
import threading
import time
import traceback
import typing
import zmq

from src.common.misc import NumpyArrayEncoder, NumpyArrayDecoder, unique_id


CONTEXT = zmq.Context()
CONTEXT.setsockopt(zmq.LINGER, 0)

REQUEST_TIMEOUT_MS = 2000


RequestType = enum.IntEnum('RequestType',
    ['quit', 'rpc']
)

ErrorType = enum.IntEnum('ErrorType',
    ['none', 'invalid_request', 'wrong_method', 'internal_error']
)

PublisherTopic = enum.IntEnum('PublisherTopic',
    ['status', 'stdout', 'stderr']
)


def remote(func):
    """ Decorator for methods that should be available over the network"""
    func.accessible_remotely = True
    return func

def _makeFun(method_name):
    def fun(self, *args, **kwargs):
        request = {
            'type': RequestType.rpc,
            'method_name': method_name,
            'args': args,
            'kwargs': kwargs,
        }
        self.client_socket.send_json(request, cls=NumpyArrayEncoder)
        
        poller = zmq.Poller()
        poller.register(self.client_socket, zmq.POLLIN)
        events = dict(poller.poll(timeout=REQUEST_TIMEOUT_MS))

        if events.get(self.client_socket) == zmq.POLLIN:
            response = self.client_socket.recv_json(cls=NumpyArrayDecoder)
            # print('remote call response: {}'.format(response))
            error = ErrorType(response.get('error'))
            if error != ErrorType.none:
                raise Exception('Invalid remote call')
            return response.get('result')
        else:
            # Timeout, socket is confused. Close and reopen to reset its state.
            self.client_socket.close()
            self.client_socket = self.zmq_context.socket(zmq.REQ)
            self.client_socket.connect('tcp://{}:{}'.format(self.host, self.req_port))
            raise ConnectionError

    return fun

def include_remote_methods(worker_class):
    """ Decorator for class to import methods with @remote decorator """
    def decorator(frontend_class):
        for name in dir(worker_class):
            method = getattr(worker_class, name)
            if not callable(method) or not hasattr(method, 'accessible_remotely'):
                continue

            try:
                fun = _makeFun(name)
                fun.__doc__ = method.__doc__
                setattr(frontend_class, name, fun)
            except:
                traceback.print_exc()
        
        return frontend_class
    return decorator


class Capture:
    """This class is used to capture stdout and stderr"""
    def __init__(self, stream):
        self.lock = threading.Lock()
        self.original_stream = stream
        self.captured_data = []

    def write(self, buffer):
        self.original_stream.write(buffer)

        with self.lock:
            lines = buffer.split('\n')
            lines = [line.strip() for line in lines]
            lines = [line for line in lines if len(line) > 0]
            self.captured_data.extend(lines)

    def flush(self):
        self.original_stream.flush()

    def get_captured_data(self):
        with self.lock:
            result = self.captured_data
            self.captured_data = []

        return result

class PeriodicTask:
    def __init__(self, zmq_context, worker: typing.Callable, period: float):
        name = unique_id(self)

        self.shutdown_send_socket = zmq_context.socket(zmq.PAIR)
        self.shutdown_send_socket.bind('inproc://shutdown_{}'.format(name))

        self.result_recv_socket = zmq_context.socket(zmq.PAIR)
        self.result_recv_socket.bind('inproc://result_{}'.format(name))

        def _worker(zmq_context, name: str, worker: typing.Callable, period: float):
            shutdown_recv_socket = zmq_context.socket(zmq.PAIR)
            shutdown_recv_socket.connect('inproc://shutdown_{}'.format(name))
            
            result_send_socket = zmq_context.socket(zmq.PAIR)
            result_send_socket.connect('inproc://result_{}'.format(name))

            poller = zmq.Poller()
            poller.register(shutdown_recv_socket, zmq.POLLIN)

            next_tick = time.time()

            while True:
                time_now = time.time()
                if time_now >= next_tick:
                    try:
                        result = worker()
                        result_send_socket.send_json(result, cls=NumpyArrayEncoder)
                    except zmq.ZMQError:
                        traceback.print_exc()
                        break
                    except:
                        traceback.print_exc()

                    next_tick = next_tick + period
                    if time_now >= next_tick:
                        print('task "{}" is taking too long'.format(target.__name__), file=sys.stderr)
                        next_tick = time_now
                    poll_timeout = 0
                else:
                    remaining_ms = 1000 * (next_tick - time_now)
                    poll_timeout = remaining_ms

                events = dict(poller.poll(timeout=poll_timeout))
                if events.get(shutdown_recv_socket) == zmq.POLLIN:
                    _ = shutdown_recv_socket.recv()
                    break

            result_send_socket.close()
            shutdown_recv_socket.close()

        self.worker_thread = threading.Thread(
            target=_worker,
            args=(zmq_context, name, worker, period),
            daemon=True
        )
        self.worker_thread.start()

        self.running = True

    def __del__(self):
        if self.running:
            self.stop()

    def stop(self):
        if self.running:
            self.running = False
            self.shutdown_send_socket.send(b'')
            self.worker_thread.join()
            self.result_recv_socket.close()
            self.shutdown_send_socket.close()

class BackgroundTask:
    def __init__(self, zmq_context, worker: typing.Callable):
        self.name = unique_id(self)

        self.result_recv_socket = zmq_context.socket(zmq.PAIR)
        self.result_recv_socket.bind('inproc://result_{}'.format(self.name))

        def _worker(zmq_context, name: str, worker: typing.Callable):
            result_send_socket = zmq_context.socket(zmq.PAIR)
            result_send_socket.connect('inproc://result_{}'.format(name))

            try:
                result = worker()
                error = None
            except Exception as e:
                traceback.print_exc()
                result = None
                error = str(e)

            result_send_socket.send_json([result, error], cls=NumpyArrayEncoder)
            result_send_socket.close()

        self.worker_thread = threading.Thread(
            target=_worker,
            args=(zmq_context, self.name, worker),
            daemon=False
        )
        self.worker_thread.start()

    def close(self):
        self.worker_thread.join()
        self.result_recv_socket.close()

# TODO rewrite this to be a class derived from PeriodicTask (?)
class Timer:
    def __init__(self, zmq_context, period: float):
        timer_name = unique_id(self)

        self.timeout_socket = zmq_context.socket(zmq.PAIR)
        self.timeout_socket.bind('inproc://timeout_{}'.format(timer_name))

        self.control_socket = zmq_context.socket(zmq.PAIR)
        self.control_socket.bind('inproc://control_{}'.format(timer_name))

        def _worker(zma_context, name: str, period: float):
            timeout_socket = zmq_context.socket(zmq.PAIR)
            timeout_socket.connect('inproc://timeout_{}'.format(name))

            control_socket = zmq_context.socket(zmq.PAIR)
            control_socket.connect('inproc://control_{}'.format(name))

            poller = zmq.Poller()
            poller.register(control_socket, zmq.POLLIN)

            next_tick = time.time()

            while True:
                time_now = time.time()
                if time_now >= next_tick:
                    timeout_socket.send(b'')
                    next_tick += period
                else:
                    remaining_ms = 1000 * (next_tick - time_now)
                    events = dict(poller.poll(timeout=remaining_ms))

                    if events.get(control_socket) == zmq.POLLIN:
                        _ = control_socket.recv()
                        break

            control_socket.close()
            timeout_socket.close()

        self.worker_thread = threading.Thread(
            target=_worker,
            args=(zmq_context, timer_name, period),
            daemon=True
        )
        self.worker_thread.start()

        self.running = True

    def __del__(self):
        if self.running:
            self.stop()

    def stop(self):
        if self.running:
            self.running = False
            self.control_socket.send(b'')
            self.worker_thread.join()
            self.control_socket.close()
            self.timeout_socket.close()


class DeviceWorker:
    def __init__(self, req_port: int, pub_port: int, refresh_period: float = 0.1):
        self.req_port = req_port
        self.pub_port = pub_port
        self.refresh_period = refresh_period

        self.should_continue = True
        self.timer_callbacks = {}
        self.periodic_task_callbacks = {}
        self.background_task_callbacks = {}
        self.socket_callbacks = {}

    @remote
    def status(self):
        return {}

    def init_device(self):
        pass

    def destroy_device(self):
        pass

    def start_timer(self, callback: typing.Callable, period: float):
        timer = Timer(self.zmq_context, period)
        self.timer_callbacks[timer] = callback
        self.poller.register(timer.timeout_socket, zmq.POLLIN)
        return timer

    def start_periodic_task(self, worker: typing.Callable, callback: typing.Callable, period: float):
        task = PeriodicTask(self.zmq_context, worker, period)
        self.periodic_task_callbacks[task] = callback
        self.poller.register(task.result_recv_socket, zmq.POLLIN)
        return task

    def start_background_task(self, worker: typing.Callable, callback: typing.Callable):
        task = BackgroundTask(self.zmq_context, worker)
        self.background_task_callbacks[task] = callback
        self.poller.register(task.result_recv_socket, zmq.POLLIN)

    def connect_to_endpoint(self, endpoint, socket_type, callback):
        socket = self.zmq_context.socket(socket_type)
        if socket_type == zmq.SUB:
            socket.setsockopt(zmq.SUBSCRIBE, b'')
        socket.connect(endpoint)
        self.socket_callbacks[socket] = callback
        self.poller.register(socket, zmq.POLLIN)

    def run(self):
        self.stdout = Capture(sys.stdout)
        sys.stdout = self.stdout
        self.stderr = Capture(sys.stderr)
        sys.stderr = self.stderr

        print('running device {}'.format(self.__class__.__name__))

        self.publish_lock = threading.Lock()

        self.zmq_context = zmq.Context()
        self.zmq_context.setsockopt(zmq.LINGER, 0)

        self.server_socket = self.zmq_context.socket(zmq.REP)
        self.server_socket.bind('tcp://*:{}'.format(self.req_port))

        self.publisher_socket = self.zmq_context.socket(zmq.PUB)
        self.publisher_socket.bind('tcp://*:{}'.format(self.pub_port))

        self.poller = zmq.Poller()
        self.poller.register(self.server_socket, zmq.POLLIN)


        print('calling init_device()')
        try:
            self.init_device()
        except:
            traceback.print_exc()

        print('starting the refresh timer')
        self.start_timer(self._refresh, self.refresh_period)

        while self.should_continue:
            try:
                events = dict(self.poller.poll(timeout=500))
            except KeyboardInterrupt:
                break

            if events.get(self.server_socket) == zmq.POLLIN:
                self._handle_server_request()

            for timer, callback in self.timer_callbacks.items():
                socket = timer.timeout_socket
                if events.get(socket) == zmq.POLLIN:
                    _ = socket.recv()
                    try:
                        callback()
                    except:
                        traceback.print_exc()

            for task, callback in self.periodic_task_callbacks.items():
                socket = task.result_recv_socket
                if events.get(socket) == zmq.POLLIN:
                    result = socket.recv_json(cls=NumpyArrayDecoder)
                    try:
                        callback(result)
                    except:
                        traceback.print_exc()

            background_tasks = list(self.background_task_callbacks.keys())
            for task in background_tasks:
                socket = task.result_recv_socket
                if events.get(socket) == zmq.POLLIN:
                    callback = self.background_task_callbacks.pop(task)
                    result, error = socket.recv_json(cls=NumpyArrayDecoder)
                    if error is not None:
                        print('error in task {}: {}'.format(task.name, error), file=sys.stderr)
                    else:
                        try:
                            callback(result)
                        except:
                            traceback.print_exc()
                    self.poller.unregister(socket)
                    task.close()
            if len(background_tasks) > 0:
                print('{} background tasks pending'.format(len(self.background_task_callbacks)))

            for socket, callback in self.socket_callbacks.items():
                if events.get(socket) == zmq.POLLIN:
                    message = socket.recv_json(cls=NumpyArrayDecoder)
                    callback(message)

        print('calling destroy_device()')
        try:
            self.destroy_device()
        except:
            traceback.print_exc()


        print('stopping timers')
        for timer in self.timer_callbacks.keys():
            timer.stop()

        print('stopping other periodic tasks')
        for task in self.periodic_task_callbacks.keys():
            task.stop()

        print('waiting for background tasks to complete')
        for task in self.background_task_callbacks.keys():
            task.close()

        print('closing dynamically bound sockets')
        for socket in self.socket_callbacks.keys():
            socket.close()

        print('closing other sockets')
        self.publisher_socket.close()
        self.server_socket.close()

        print('destroying the zmq context')
        self.zmq_context.term()

        print('finally the whole process quits')

    def _handle_server_request(self):
        try:
            request = self.server_socket.recv_json(cls=NumpyArrayDecoder)
            request_type = request['type']
            # print('received a request: {}'.format(request))
            
            if request_type == RequestType.quit:
                response = dict(error=ErrorType.none, result=None)
                self.server_socket.send_json(response, cls=NumpyArrayEncoder)
                self.should_continue = False
                return

            elif request_type == RequestType.rpc:
                method_name = request['method_name']
                args = request['args']
                kwargs = request['kwargs']

                try:
                    method = getattr(self, method_name)
                except AttributeError:
                    traceback.print_exc()
                    response = dict(error=ErrorType.wrong_method, result=None)
                    self.server_socket.send_json(response, cls=NumpyArrayEncoder)
                    return

                try:
                    result = method(*args, **kwargs)
                    response = dict(error=ErrorType.none, result=result)
                except:
                    traceback.print_exc()
                    response = dict(error=ErrorType.internal_error, result=None)
                    self.server_socket.send_json(response, cls=NumpyArrayEncoder)
                    return

                self.server_socket.send_json(response, cls=NumpyArrayEncoder)

        except KeyError:
            traceback.print_exc()
            response = dict(error=ErrorType.invalid_request, result=None)
            self.server_socket.send_json(response, cls=NumpyArrayEncoder)

        except zmq.ZMQError:
            traceback.print_exc()
            self.should_continue = False

    def _publish_msg(self, topic, contents):
        try:
            message = dict(topic=topic, contents=contents)
            self.publisher_socket.send_json(message, cls=NumpyArrayEncoder)
        except zmq.ZMQError:
            traceback.print_exc()

    def _refresh(self):
        try:
            # print('time to refresh')

            try:
                self._publish_msg(PublisherTopic.status, self.status())
            except:
                traceback.print_exc()

            try:
                self._publish_msg(PublisherTopic.stdout, self.stdout.get_captured_data())
            except:
                traceback.print_exc()

            try:
                self._publish_msg(PublisherTopic.stderr, self.stderr.get_captured_data())
            except:
                traceback.print_exc()

        except zmq.ZMQError:
            traceback.print_exc()


@include_remote_methods(DeviceWorker)
class DeviceInterface:
    def __init__(self, req_port: int, pub_port: int, host="localhost", zmq_context = None):
        self.host = host
        self.pub_port = pub_port
        self.req_port = req_port

        self.zmq_context = zmq_context or CONTEXT

        self.client_socket = self.zmq_context.socket(zmq.REQ)
        self.client_socket.connect('tcp://{}:{}'.format(host, req_port))

        self.listeners = []

        self.open = True

    def stop(self):
        """Stops the remote device and closes the interface"""
        self.client_socket.send_json(dict(type=RequestType.quit), cls=NumpyArrayEncoder)
        self.close()

    def close(self):
        """Closes the interface"""
        self.open = False
        for listener in self.listeners:
            listener.stop()
        self.client_socket.close()

    class Subscriber:
        def __init__(self, zmq_context, callback, topics, host, pub_port):
            subscriber_name = id(self)

            self.control_socket = zmq_context.socket(zmq.PAIR)
            self.control_socket.bind('inproc://control_{}'.format(subscriber_name))

            def _worker():
                subscriber_socket = zmq_context.socket(zmq.SUB)
                subscriber_socket.setsockopt(zmq.SUBSCRIBE, b'')
                subscriber_socket.connect('tcp://{}:{}'.format(host, pub_port))

                control_socket = zmq_context.socket(zmq.PAIR)
                control_socket.connect('inproc://control_{}'.format(subscriber_name))

                poller = zmq.Poller()
                poller.register(subscriber_socket, zmq.POLLIN)
                poller.register(control_socket, zmq.POLLIN)

                while True:
                    events = dict(poller.poll())

                    if events.get(control_socket) == zmq.POLLIN:
                        _ = control_socket.recv()
                        break

                    if events.get(subscriber_socket) == zmq.POLLIN:
                        msg = subscriber_socket.recv_json(cls=NumpyArrayDecoder)
                        if msg.get('topic') in topics:
                            callback(msg.get('contents'))

                control_socket.close()
                subscriber_socket.close()

            self.worker_thread = threading.Thread(target=_worker, daemon=True)
            self.worker_thread.start()

            self.running = True

        def __del__(self):
            if self.running:
                self.stop()

        def stop(self):
            if self.running:
                self.running = False
                self.control_socket.send(b'')
                self.worker_thread.join()
                self.control_socket.close()

    def create_listener_thread(self, callback, topics = (PublisherTopic.status,)):
        subscriber = DeviceInterface.Subscriber(self.zmq_context, callback, topics, self.host, self.pub_port)
        self.listeners.append(subscriber)
