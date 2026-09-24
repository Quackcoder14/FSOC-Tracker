# FSOC Tracker

A real-time optical tracking system for Free-Space Optical Communication (FSOC) coarse alignment, featuring a React frontend and Python backend with WebSocket communication.

## Features

- **Real-time Tracking**: Live optical tracking with Kalman filter prediction
- **Simulation Mode**: Virtual beacon simulation for testing and development
- **Benchmark Mode**: Video-based benchmarking with ground truth evaluation
- **Live Telemetry**: Real-time metrics (RMSE, lock retention, FPS, latency)
- **Report Generation**: Automated HTML and JSON report generation
- **3D Visualization**: Interactive 3D world view with Three.js
- **Split View**: Side-by-side camera POV and world view
- **Run History**: Track and export simulation and benchmark runs

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Dashboard    │  │ Simulation   │  │ Benchmark    │      │
│  │ View         │  │ Controls     │  │ View         │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Scientific   │  │ Reports      │  │ World View   │      │
│  │ Debug        │  │ View         │  │ (Three.js)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└──────────────────────────┬──────────────────────────────────┘
                           │ WebSocket (ws://)
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                    Backend (Python)                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  WebSocket Server (port 8765)                         │   │
│  │  - Command dispatch                                   │   │
│  │  - Telemetry broadcast                                │   │
│  │  - Status updates                                     │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  HTTP Upload Server (port 8766)                       │   │
│  │  - Video file upload                                  │   │
│  │  - Ground truth upload                               │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Engine Core                                           │   │
│  │  - Frame source (simulation/video)                     │   │
│  │  - Detection pipeline                                 │   │
│  │  - Tracking (Kalman filter)                           │   │
│  │  - Control (PID controller)                           │   │
│  │  - Evaluation (RMSE, lock retention)                  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

- **Python**: 3.10 or higher
- **Node.js**: 18 or higher
- **npm**: 9 or higher

## Local Development Setup

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Start the backend server:
```bash
python main.py
```

The backend will start:
- WebSocket server on `ws://127.0.0.1:8765`
- HTTP upload server on `http://127.0.0.1:8766`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create environment file (optional):
```bash
cp .env.example .env
```

Edit `.env` to configure the backend WebSocket URL:
```
VITE_BACKEND_WS_URL=ws://localhost:8765
```

4. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

### Running the Application

1. Start the backend server (if not already running)
2. Start the frontend server
3. Open `http://localhost:3000` in your browser
4. The application will automatically connect to the backend

## Configuration

### Backend Configuration

The backend uses YAML configuration files located in `backend/configs/`. The default configuration is in `backend/configs/default.yaml`.

Key configuration options:
- `system.target_fps`: Target frames per second for the engine
- `camera.resolution`: Camera resolution (width, height)
- `camera.hfov_deg`: Horizontal field of view in degrees
- `tracking.acquisition_frames`: Frames required for initial lock
- `kalman.process_noise`: Kalman filter process noise parameter
- `kalman.measurement_noise`: Kalman filter measurement noise parameter

### Frontend Configuration

The frontend uses environment variables:
- `VITE_BACKEND_WS_URL`: WebSocket URL of the backend (default: `ws://127.0.0.1:8765`)

## Deployment

This application uses a hybrid deployment strategy:
- **Backend**: Render (Python web service with long-running WebSocket/HTTP servers)
- **Frontend**: Vercel (static site)

### Prerequisites

- Render account (free tier available)
- Vercel account (free tier available)
- Git repository with the code

### Backend Deployment (Render)

1. **Create a new Web Service** on Render
2. Connect your Git repository
3. Configure the service:
   - **Name**: `fsoc-tracker-backend`
   - **Runtime**: Python 3
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py --host 0.0.0.0 --port 8765 --http-port 8766`
4. Click "Deploy"

Render will automatically detect the `Procfile` in the backend directory.

### Frontend Deployment (Vercel)

1. **Create a new project** on Vercel
2. Connect your Git repository
3. Configure the project:
   - **Framework Preset**: Vite
   - **Root Directory**: `./` (root of repository)
   - **Build Command**: `cd frontend && npm install && npm run build`
   - **Output Directory**: `frontend/dist`
4. Add Environment Variable:
   - **Key**: `VITE_BACKEND_WS_URL`
   - **Value**: `wss://fsoc-tracker-backend.onrender.com` (replace with your actual backend URL)
5. Click "Deploy"

The `vercel.json` file in the repository root provides the necessary configuration for Vercel.

### Post-Deployment Configuration

After both services are deployed:

1. Get your backend URL from Render (e.g., `https://fsoc-tracker-backend.onrender.com`)
2. Update the frontend environment variable:
   - Go to your Vercel project → Settings → Environment Variables
   - Update `VITE_BACKEND_WS_URL` to `wss://your-backend-url.onrender.com`
3. Redeploy the Vercel project

### Troubleshooting Deployment

**Backend fails to start:**
- Check the Render logs for error messages
- Ensure all dependencies in `requirements.txt` are compatible
- Verify the start command is correct
- Make sure the build command includes `cd backend`

**Frontend can't connect to backend:**
- Ensure both services are running
- Check that `VITE_BACKEND_WS_URL` is set correctly (use `wss://` for HTTPS)
- Verify the backend WebSocket server is accessible
- Check Vercel deployment logs for any build errors

**WebSocket connection issues:**
- Render uses HTTPS, so use `wss://` for WebSocket URLs
- Check that the backend is binding to `0.0.0.0` (not `127.0.0.1`)
- Verify Render's network allows WebSocket connections
- Check that the backend service is not in a suspended state

## Usage

### Simulation Mode

1. Navigate to the "Simulation" tab
2. Click "Start Simulation" to begin the virtual beacon simulation
3. Use the controls to adjust parameters:
   - Beacon size
   - Motion speed
   - Noise levels
4. Observe real-time tracking metrics in the dashboard

### Benchmark Mode

1. Navigate to the "Benchmark" tab
2. Select a video file (upload or provide path)
3. Optionally select a ground truth file
4. Click "Start Benchmark"
5. The system will process the video and evaluate tracking performance
6. View results in the "Results" tab

### Reports

1. Navigate to the "Results" tab
2. View run history with metrics (RMSE, lock retention, FPS, latency)
3. Click "Download Report" to export all runs as CSV
4. Click on individual runs to view detailed metrics

## Troubleshooting

### Backend Issues

**Port already in use:**
```bash
# Find process using the port
netstat -ano | findstr :8765
# Kill the process
taskkill /F /PID <PID>
```

**Import errors:**
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version compatibility (3.10+)

### Frontend Issues

**WebSocket connection failed:**
- Ensure the backend is running
- Check that `VITE_BACKEND_WS_URL` is set correctly
- Verify the backend WebSocket server is accessible

**Build errors:**
- Clear node_modules and reinstall: `rm -rf node_modules && npm install`
- Check Node.js version (18+ required)

### General Issues

**Performance issues:**
- Reduce target FPS in configuration
- Lower camera resolution
- Disable 3D visualization if not needed

**Tracking not working:**
- Check beacon detection threshold in configuration
- Adjust Kalman filter parameters
- Verify camera calibration

## Development

### Backend Development

Run tests:
```bash
cd backend
pytest
```

### Frontend Development

The frontend uses Vite for fast development with hot module replacement.

Build for production:
```bash
cd frontend
npm run build
```

Preview production build:
```bash
npm run preview
```

## Project Structure

```
fsoc-tracker/
├── backend/
│   ├── app/
│   │   ├── communication/    # WebSocket and HTTP servers
│   │   ├── config/          # Configuration loading
│   │   ├── control/         # PID controller
│   │   ├── core/            # Engine core
│   │   ├── detection/       # Beacon detection
│   │   ├── evaluation/      # Performance evaluation
│   │   ├── input/           # Frame sources
│   │   ├── logging/         # Logging utilities
│   │   ├── simulation/      # Simulation engine
│   │   └── tracking/        # Kalman filter tracking
│   ├── configs/             # YAML configuration files
│   ├── main.py              # Backend entry point
│   ├── requirements.txt     # Python dependencies
│   └── Procfile             # Render deployment config
├── frontend/
│   ├── src/
│   │   ├── canvas/          # Canvas components
│   │   ├── components/     # UI components
│   │   ├── services/        # WebSocket service
│   │   ├── types/           # TypeScript types
│   │   ├── views/           # Page views
│   │   ├── worldView/       # 3D world view
│   │   ├── App.tsx          # Main app component
│   │   └── vite-env.d.ts    # Vite type definitions
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── .env.example
├── data/                    # Test data
├── models/                  # ML models
├── results/                 # Generated reports
├── render.yaml              # Render service configuration
└── README.md
```

## License

This project is part of the FSOC Tracker system. See LICENSE file for details.

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For issues and questions:
- Open an issue on GitHub
- Check the troubleshooting section
- Review the configuration documentation
