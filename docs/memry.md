# Memory / Knowledge
- Fixed bug where camera_stream_manager.sessions caused an AttributeError preventing bounding boxes from rendering. Replaced with _streams.
- Handled ROI polygons correctly to ignore wall pictures and tables.
