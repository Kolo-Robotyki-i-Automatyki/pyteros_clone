#!/usr/bin/env python3

import fractions
import json
import re
import subprocess
import threading
import time
import zmq


PORT = 8000


RE_INDEX = re.compile(r"\s*Index\s*:\s([0-9]+)\s*")
RE_TYPE = re.compile(r"\s*Type\s*:\s*(.*)\s*")
RE_PIXEL_FORMAT = re.compile(r"\s*Pixel Format\s*:\s*'([^']*)'.*")
RE_NAME = re.compile(r"\s*Name\s*:\s*(.*)\s*")
RE_SIZE = re.compile(r"\s*Size[^0-9]*([0-9]+)x([0-9]+)\s*")
RE_INTERVAL = re.compile(r"\s*Interval[^(]*\(([0-9]+\.[0-9]+)\s*fps\)\s*")


class FormatNotSupportedError(Exception):
    pass

def _get_video_devices():
    list_devices_process = subprocess.run(['v4l2-ctl', '--list-devices'], stdout=subprocess.PIPE)
    
    devices = {}

    current_name = ''
    for line in list_devices_process.stdout.decode('utf-8').split('\n'):
        if len(line.strip()) == 0:
            continue

        if line[0].isspace():
            devices[line.strip()] = current_name
        else:
            current_name = line.strip()[:-1]

    return devices

def _get_video_formats(device_name):
    command = ['v4l2-ctl', '--list-formats-ext', '-d', device_name]
    list_formats_process = subprocess.run(command, stdout=subprocess.PIPE)

    formats = []

    lines = list_formats_process.stdout.decode('utf-8').split('\n')
    lines = [line.strip() for line in lines if len(line.strip()) > 0]

    i = 0
    while i < len(lines):
        if RE_INDEX.match(lines[i]) is None:
            i += 1
            continue

        index = int(RE_INDEX.match(lines[i]).groups()[0])
        i += 1
        devtype = RE_TYPE.match(lines[i]).groups()[0].strip()
        i += 1
        pixel_format = RE_PIXEL_FORMAT.match(lines[i]).groups()[0].strip()
        i += 1
        name = RE_NAME.match(lines[i]).groups()[0].strip()
        i += 1
        
        format_description = {
            'index': index,
            'type': devtype,
            'pixel format': pixel_format,
            'name': name,
            'framesizes': [],
        }

        while i < len(lines):
            size_match = RE_SIZE.match(lines[i])
            if size_match is None:
                break

            width, height = (int(x) for x in size_match.groups())
            i += 1
            
            while i < len(lines):
                interval_match = RE_INTERVAL.match(lines[i])
                if interval_match is None:
                    break

                fps = float(interval_match.groups()[0])
                i += 1

                format_description['framesizes'].append({
                    'width': width,
                    'height': height,
                    'fps': fps
                })

        formats.append(format_description)

    return formats

def _create_pipeline(device, pixel_format, width, height, fps, host, port):
    prefix = 'gst-launch-1.0 v4l2src device={}'.format(device)
    suffix = 'udpsink host={} port={}'.format(host, port)

    fps_fraction = fractions.Fraction(float(fps))
    fps_str = '{}/{}'.format(fps_fraction.numerator, fps_fraction.denominator)

    if 'MJPG' in pixel_format:
        middle = 'image/jpeg, width={}, height={}, framerate={} ! rtpjpegpay'.format(width, height, fps_str)
        return ' ! '.join([prefix, middle, suffix])
    elif 'H264' in pixel_format:
        middle = 'video/x-h264, width={}, height={}, framerate={} ! rtph264pay'.format(width, height, fps_str)
        return ' ! '.join([prefix, middle, suffix])
    else:
        raise FormatNotSupportedError('Pixel format {} not supported'.format(pixel_format))

class CameraServer:
    def __init__(self):
        self.zmq_context = zmq.Context()
        self.socket = self.zmq_context.socket(zmq.REP)
        self.socket.bind('tcp://0.0.0.0:{}'.format(PORT))

        self._load_camera_info()

    def _load_camera_info(self):
        subprocess.run('pkill gst-launch-1.0'.split())
        
        self.streams = {device: None for device, name in _get_video_devices().items()}
        self.formats = {device: _get_video_formats(device) for device in self.streams}

    def run(self):
        while True:
            try:
                request = self.socket.recv().decode('utf-8').split()
            
                command = request[0] if len(request) > 0 else ''

                if command == 'STREAMS':
                    self._respond_streams(request)
                elif command == 'FORMATS':
                    self._respond_formats(request)
                elif command == 'START':
                    self._respond_start_stream(request)
                elif command == 'STOP':
                    self._respond_stop_stream(request)
                elif command == 'RESET':
                    self._respond_reset(request)
                else:
                    self._respond_error(request, ['Unknown command "{}"'.format(command)])
            except Exception as err:
                print("Exception occured while handling a request")
                print(err)

                try:
                    self._respond_error(request, ['Internal error'])
                except:
                    pass

    def _respond_error(self, request, error_messages=[]):
        response = 'ERROR\n' + ''.join(line + '\n' for line in error_messages)
        self.socket.send_string(response)

    def _respond_streams(self, request):
        if len(request) != 1:
            self._respond_error(request, 'Expected "STREAMS"')
            return

        streams = {device: stream[1] if stream is not None else None for device, stream in self.streams.items()}
        response = json.dumps(streams, sort_keys=True, indent=2)
        self.socket.send_string(response)

    def _respond_formats(self, request):
        if len(request) != 1:
            self._respond_error(request, 'Expected "FORMATS"')
            return

        response = json.dumps(self.formats, sort_keys=True, indent=2)
        self.socket.send_string(response)

    def _launch_gst_pipeline(self, device, pipeline, stream_info):
        gst_process = subprocess.Popen(pipeline.split())
        self.streams[device] = gst_process, stream_info
        gst_process.wait()
        self.streams[device] = None

    def _respond_start_stream(self, request):
        if len(request) != 8:
            self._respond_error(
                request,
                ['Expected "START <device> <format> <width> <height> <fps> <host ip> <host port>"'])
            return

        device = request[1]
        encoding = request[2]
        width = request[3]
        height = request[4]
        fps = request[5]
        host_ip = request[6]
        host_port = request[7]

        if device not in self.streams:
            self._respond_error(request, ['Unknown device "{}"'.format(device)])
            return

        if self.streams[device] is not None:
            self._respond_error(request, ['Device {} is busy'.format(device)])
            return

        try:
            pipeline = _create_pipeline(*request[1:8])
        except FormatNotSupportedError as err:
            self._respond_error(request, [str(err)])
            return

        stream_info = (host_ip, host_port, encoding, width, height, fps)

        print('starting new pipeline:\n{}'.format(pipeline))

        pipeline_thread = threading.Thread(
            target=self._launch_gst_pipeline,
            args=(device, pipeline, stream_info),
            daemon=True)
        pipeline_thread.start()

        self.socket.send_string('OK\n')

    def _respond_stop_stream(self, request):
        if len(request) != 2:
            self._respond_error(
                request,
                ['Expected "STOP <device>"'])
            return

        device = request[1]
        if device not in self.streams:
            self._respond_error(request, ['Unknown device "{}"'.format(device)])
            return

        if self.streams[device] is None:
            self._respond_error(request, ['Device {} is not currently in use'.format(device)])
            return

        stream_process, _ = self.streams[device]
        stream_process.terminate()
        self.streams[device] = None

        self.socket.send_string('OK\n')

    def _respond_reset(self, request):
        if len(request) != 1:
            self._respond_error(request, 'Expected "RESET"')
            return

        self._load_camera_info()

        self.socket.send_string('OK\n')

if __name__ == '__main__':
    devices = _get_video_devices()

    for device, name in devices.items():
        print('{} -- {}:'.format(device, name))

        formats = _get_video_formats(device)
        for format_description in formats:
            print('\t{}:'.format(format_description['name']))
            for frame in format_description['framesizes']:
                print('\t\t{}x{} @ {} fps'.format(frame['width'], frame['height'], frame['fps']))

 
    server = CameraServer()
    server.run()
