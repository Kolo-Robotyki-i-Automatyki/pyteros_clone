#include <gst/gst.h>
#include <gst/video/videooverlay.h>
#include <glib.h>	

#include <functional>
#include <iostream>
#include <string>


int WINDOW_ID = 174063681;


namespace {

gboolean bus_call (GstBus* bus, GstMessage* msg, gpointer data) {
	GMainLoop *loop = (GMainLoop*) data;

	switch (GST_MESSAGE_TYPE (msg)) {
	case GST_MESSAGE_EOS:
		g_print ("End of stream\n");
		g_main_loop_quit (loop);
		break;

	case GST_MESSAGE_ERROR: {
		gchar  *debug;
		GError *error;

		gst_message_parse_error (msg, &error, &debug);
		g_free (debug);

		g_printerr ("Error: %s\n", error->message);
		g_error_free (error);

		g_main_loop_quit (loop);
		break;
	}

	default:
		break;
	}

	return TRUE;
}

GstBusSyncReply bus_sync (GstBus* bus, GstMessage* message, GstPipeline* pipeline) {
	// ignore anything but 'prepare-window-handle' element messages
	if (!gst_is_video_overlay_prepare_window_handle_message (message))
		return GST_BUS_PASS;

	gst_video_overlay_set_window_handle (GST_VIDEO_OVERLAY (GST_MESSAGE_SRC (message)), WINDOW_ID);

	gst_message_unref(message);

	return GST_BUS_DROP;
}

GstElement* create_pipeline(int port, std::string format, int video_direction) {
	GstElement *pipeline;
	pipeline = gst_pipeline_new("custom-pipeline");

	GstElement *udp_source, *flipper, *x_sink;

	udp_source = gst_element_factory_make("udpsrc", NULL);
	g_object_set(G_OBJECT(udp_source), "port", port, NULL);

	flipper = gst_element_factory_make("videoflip", NULL);
	g_object_set(G_OBJECT(flipper), "video-direction", video_direction, NULL);

	x_sink = gst_element_factory_make("ximagesink", NULL);
	// g_object_set(G_OBJECT(x_sink), "force-aspect-ratio", true, NULL);

	if (format == "MJPG") {
		// gst-launch-1.0 udpsrc port=9000 ! application/x-rtp,encoding-name=JPEG,payload=26 ! rtpjpegdepay ! jpegdec ! videoflip ! autovideoconvert ! ximagesink

		GstElement *depayloader, *decoder, *converter;
		depayloader = gst_element_factory_make("rtpjpegdepay", NULL);
		decoder = gst_element_factory_make("jpegdec", NULL);
		converter = gst_element_factory_make("autovideoconvert", NULL);

		GstCaps* src_caps = gst_caps_new_full (
		  	gst_structure_new ("application/x-rtp",
				"encoding-name", G_TYPE_STRING, "JPEG",
				"payload", G_TYPE_INT, 26,
				NULL),
			NULL);

		if (!pipeline | !udp_source | !depayloader | !decoder | !flipper | !converter | !x_sink | !src_caps)
			return nullptr;

		gst_bin_add_many(GST_BIN (pipeline), udp_source, depayloader, decoder, flipper, converter, x_sink, NULL);
		gst_element_link_filtered(udp_source, depayloader, src_caps);
		gst_element_link_many(depayloader, decoder, flipper, converter,
			x_sink, NULL);

		gst_caps_unref(src_caps);

	} else if (format == "H264") {
		// gst-launch-1.0 udpsrc port=9000 ! "application/x-rtp, payload=96" ! rtph264depay ! avdec_h264 ! videoflip ! autovideoconvert ! xvimagesink

		GstElement *depayloader, *decoder, *converter;
		depayloader = gst_element_factory_make("rtph264depay", NULL);
		decoder = gst_element_factory_make("avdec_h264", NULL);
		converter = gst_element_factory_make("autovideoconvert", NULL);

		GstCaps* src_caps = gst_caps_new_full (
		  	gst_structure_new ("application/x-rtp",
				"encoding-name", G_TYPE_STRING, "H264",
				"payload", G_TYPE_INT, 96,
				NULL),
			NULL);

		if (!pipeline | !udp_source | !depayloader | !decoder | !flipper | !converter | !x_sink | !src_caps)
			return nullptr;

		gst_bin_add_many(GST_BIN (pipeline), udp_source, depayloader, decoder, flipper, converter, x_sink, NULL);
		gst_element_link_filtered(udp_source, depayloader, src_caps);
		gst_element_link_many(depayloader, decoder, flipper, converter, x_sink, NULL);

		gst_caps_unref(src_caps);

	} else {
		return nullptr;
	}

	return pipeline;
}

}

int main (int argc, char *argv[]) {
	if (argc != 5) {
		std::cerr << "Usage: " << argv[0] << " <port> <format> <video direction> <window id>" << std::endl;
		return -1;
	}

	int port = std::atoi(argv[1]);
	std::string format = argv[2];
	int video_direction = std::atoi(argv[3]);
	WINDOW_ID = std::atoi(argv[4]);

	gst_init (&argc, &argv);

	GMainLoop* loop = g_main_loop_new (NULL, FALSE);

	GstElement* pipeline = ::create_pipeline(port, format, video_direction);
	if (pipeline == nullptr) {
		std::cerr << "Failed to create pipeline" << std::endl;
		return -2;
	}

	GstBus* bus = gst_pipeline_get_bus (GST_PIPELINE (pipeline));
	guint bus_watch_id = gst_bus_add_watch (bus, ::bus_call, loop);
	gst_bus_set_sync_handler(bus, (GstBusSyncHandler) ::bus_sync, pipeline, NULL);
	gst_object_unref (bus);

	gst_element_set_state (pipeline, GST_STATE_PLAYING);
	g_main_loop_run (loop);

	gst_element_set_state (pipeline, GST_STATE_NULL);
	gst_object_unref (GST_OBJECT (pipeline));
	g_main_loop_unref (loop);

	return 0;
}
