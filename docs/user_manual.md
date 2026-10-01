# User Manual

## System Requirements
- Python 3.9+
- Node.js 18+
- Modern Web Browser (Chrome/Firefox/Edge)

## Running the Backend
1. Navigate to etail-exit-backend/.
2. Activate your virtual environment.
3. Start the server using Uvicorn:
   `\ash
   python -m uvicorn src.main:app --port 8000 --host 127.0.0.1 --reload
   `\
4. The API and background worker processes will automatically initialize. WebSockets and MJPEG stream managers will listen for active camera connections.

## Running the Frontend Console
1. Navigate to etail-exit-console/.
2. Install dependencies: 
pm install.
3. Start the development server:
   `\ash
   npm run dev
   `\
4. Open the provided localhost URL in your browser to access the Smart Wall.

## Operational Workflows
### Adding a Camera
Navigate to the "Cameras" tab and input the RTSP URL or physical camera ID. Configure regions of interest (ROI) via the visual interface to ignore static elements like shelves or wall pictures.
### Reviewing Alerts
Alerts are dynamically generated when motion triggers object detection. Use the timeline to investigate items flagged as missing or unverified carriers.
