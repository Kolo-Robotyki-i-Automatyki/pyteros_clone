#!/usr/bin/python2

import rospy
import time
import posix_ipc
import argparse
from ar_track_alvar_msgs.msg import AlvarMarkers

class TagProxy(object):
	def __init__(self, queue_name):
		rospy.init_node('tag_detector', anonymous=True)
		self._detected_markers = {}
		self._queue = posix_ipc.MessageQueue(name=queue_name, flags=posix_ipc.O_CREAT)
		self._sub = rospy.Subscriber('/ar_pose_marker', AlvarMarkers, self._receive_marker)

	def _receive_marker(self, msg):
		markers = msg.markers

		for marker in markers:
			id = marker.id
			position = (getattr(marker.pose.pose.position, axis) for axis in ['x', 'y', 'z'])
			output = '{} {} {} {}'.format(id, *position)
			self._queue.send(output)

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('queue_name', type=str)
	args = parser.parse_args()

	proxy = TagProxy(args.queue_name)
	rospy.spin()
