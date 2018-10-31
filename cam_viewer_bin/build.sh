g++ cam_viewer.cpp $(pkg-config --cflags --libs gstreamer-1.0 gstreamer-video-1.0) -o cam_viewer
mv cam_viewer ../

