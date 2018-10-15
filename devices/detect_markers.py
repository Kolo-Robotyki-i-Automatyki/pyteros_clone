#!/usr/bin/python

import rospy
import time
from ar_track_alvar_msgs.msg import AlvarMarkers

MARKER_LIFESPAN = 0.2

class TagDetector(object):
    def __init__(self):
        rospy.init_node('tag_detector', anonymous=True)
        self._detected_markers = {}
        self._sub = rospy.Subscriber('/ar_pose_marker', AlvarMarkers, self._save_markers)

    def _save_markers(self, msg):
        markers = msg.markers

        for marker in markers:
            id = marker.id
            position = (getattr(marker.pose.pose.position, axis) for axis in ['x', 'y', 'z'])

            self._detected_markers[id] = (time.time(), position)

    def _filter_markers(self):
        timestamp_now = time.time()

        for id, (timestamp, _) in self._detected_markers.items():
            if timestamp_now - timestamp > MARKER_LIFESPAN:
                self._detected_markers.pop(id)

    def get_markers(self):
        self._filter_markers()
        return [(id, position) for id, (_, position) in self._detected_markers.items()]


if __name__ == '__main__':
    detector = TagDetector()

    while True:
        for id, position in detector.get_markers():
            print('{:>4}: {}, {}, {}'.format(id, *position))
        print('----------')

        time.sleep(1.0)
