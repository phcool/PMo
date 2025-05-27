# DLmonitor
The server is now running on http://47.88.7.178:8000/
## Project Structure

```
|-- backend/      # FastAPI backend
|   |-- alembic/    # database migration tool
|
|   |-- app/        # Main application folder
|   |   |-- api/        # API routers
|   |   |   |-- chat.py
|   |   |   |-- paper.py
|   |   |   |-- search.py
|   |   |   |-- user.py
|   |  
|   |   |-- db/         # database operation 
|   |   |   |-- database.py
|   |  
|   |   |-- models/     # define pydantic model
|   |   |   |-- db_models.py
|   |   |   |-- paper.py
|   |
|   |   |-- services/   # functions for api
|   |   |   |-- arxiv_search_service.py
|   |   |   |-- arxiv_service.py
|   |   |   |-- chat_service.py
|   |   |   |-- db_service.py
|   |   |   |-- llm_service.py
|   |   |   |-- pdf_service.py
|   |   |   |-- vector_search_service.py
|   |
|   |   |-- main.py     # FastAPI app entry point
|
|   |-- data/        # data folder
|
|   |-- logs/        # running log
|   
|   |-- scripts/     # scripts folder
|   |   |-- fetch_papers.py    # fetch papers from arxiv
|   |   |-- setup_cron.sh      # setup a cron to fetch papers automatically
|
|   |-- run.py       # start backened server
|   |-- start_server.sh      # run server background 
|   |-- requirements.txt     # Backend dependencies
|
|-- frontend/     # Vue frontend
|   |-- src/        # Source files
|   |   |-- components/    # Vue modules for views
|   |   |   |-- ChatButton.vue
|   |   |   |-- FileList.vue
|   |   |   |-- PaperCard.vue
|   |   |   |-- PdfViewer.vue
|   |   |   |-- SearchBox.vue
|   |   |    
|   |   |-- router/        
|   |   |   |-- index.ts   # define router structure 
|   |   |
|   |   |-- services/  
|   |   |   |-- api.ts     # handle request to backend
|   |   |
|   |   |-- stores/        # store session data
|   |   |   |-- chatSession.ts
|   |   |   |-- paperStore.ts
|   |   |   |-- searchStore.ts
|   |   |   
|   |   |-- types/         # define certain types
|   |   |   |-- paper.ts
|   |   |
|   |   |-- views/         # define pages
|   |   |   |-- ChatView.vue
|   |   |   |-- HomeView.vue
|   |   |   |-- NotFoundView.vue
|   |   |   |-- PaperDetailView.vue
|   |   |   |-- SearchView.vue
|   |
|   |   |-- main.js   # Vue app entry point
|   |   |-- App.vue
|   |
|   |-- index.html
|   |-- tsconfig.json
|   |-- tsconfig.node.json
|   |-- vite.config.ts
|   |-- package.json 
|   |
|-- .gitignore
|-- README.md
```

## Key Files Description

*   `backend/main.py`: The main entry point for the FastAPI application.
*   `backend/requirements.txt`: Lists all Python dependencies for the backend.
*   `frontend/src/main.js`: The main entry point for the Vue.js application.
*   `frontend/package.json`: Lists all Node.js dependencies and scripts for the frontend.
*   `frontend/src/router/index.js` (or `.ts`): Defines the frontend routes.
*   *(Add other important files and their descriptions here)*

## Prerequisites

Before you begin, ensure you have met the following requirements:

*   You have installed the latest version of [Node.js and npm](https://nodejs.org/en/download/)
*   You have installed [Python](https://www.python.org/downloads/) (version 3.7+ recommended)
*   You have a package manager for Python like `pip` installed.
*   *(Add any other prerequisites like database, Docker, etc.)*

## Installation

To install the project, follow these steps:

**1. Clone the repository:**

```bash
git clone <your-repository-url>
cd <project-directory-name>
```

**2. Backend Setup:**

```bash
cd backend

# Create and activate a virtual environment (recommended)
python -m venv venv
# On Windows:
# venv\Scripts\activate
# On macOS/Linux:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
cd ..
```

**3. Frontend Setup:**

```bash
cd frontend

# Install dependencies
npm install
cd ..
```

## Running the Application

**1. Start the Backend (FastAPI):**

Navigate to the `backend` directory and run:

```bash
cd backend
# If you activated a virtual environment, ensure it's still active
# source venv/bin/activate

uvicorn app.main:app --reload
# The backend will typically run on http://127.0.0.1:8000
cd ..
```
*Make sure `app.main:app` matches your FastAPI application instance location.*

**2. Start the Frontend (Vue):**

Navigate to the `frontend` directory and run:

```bash
cd frontend
npm run serve
# The frontend will typically run on http://localhost:8080 (or another port specified in your Vue config)
cd ..
```

After both frontend and backend are running, open your browser and navigate to the frontend URL (usually `http://localhost:8080`).

## Building for Production

**1. Frontend:**

```bash
cd frontend
npm run build
cd ..
```
This will create a `dist` folder in the `frontend` directory with the production-ready static files. You'll need to configure your web server (e.g., Nginx, Apache) or FastAPI (for serving static files) to serve these files.

**2. Backend:**
For the backend, ensure your production environment has all necessary dependencies installed. You might use a process manager like Gunicorn with Uvicorn workers for a robust setup.

Example with Gunicorn:
```bash
# (Inside backend directory, with virtualenv activated)
# pip install gunicorn  (if not already in requirements.txt)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app
```

## Deployment

*(Provide instructions on how to deploy your application. This can include steps for Docker, cloud platforms like Heroku, AWS, Azure, Vercel (for frontend), etc.)*

Example:
*   **Option 1: Deploying as separate services.**
*   **Option 2: Serving frontend from FastAPI.**
*   **Option 3: Using Docker.**

## API Endpoints

*(Optional: List key API endpoints and a brief description. You can also link to your API documentation, e.g., FastAPI's auto-generated docs at `/docs`)*

*   `GET /api/v1/items/`: Retrieves a list of items.
*   `POST /api/v1/items/`: Creates a new item.
*   ...

## Contributing

Contributions are welcome! Please follow these steps:

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## License

Distributed under the MIT License. See `LICENSE` for more information.
*(Or specify your chosen license)*

## Contact

Your Name - your.email@example.com

Project Link: [https://github.com/your_username/your_repository](https://github.com/your_username/your_repository)
