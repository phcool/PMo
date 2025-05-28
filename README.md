# DLmonitor
The server is now running on http://47.88.7.178:80/
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

## Setup

**1. Clone the repository:**

```bash
git clone https://github.com/phcool/PMo.git
cd PMo
```

**2. Backend Setup:**

make .env file
```bash
cd backend
touch .env
vim .env

DATABASE_URL=postgresql://postgres:password@localhost:5432/database
LLM_API_KEY=your_api_key
LLM_API_URL=your_api_url
```

install requirements
```bash
cd backend
pip install -r requirements.txt
cd ..
```

config database , currently using v=16 ( use your own verison )
```bash
"install postgresql"

sudo apt install postgresql postgresql-contrib
sudo systemctl enable --now postgresql@16-main

"start and check status"

sudo systemctl start postgresql
sudo systemctl status postgresql
```

```bash
cd backend

sudo -i -u postgres
psql
CREATE DATABASE dlmonitor;

\q
exit

alembic upgrade head

```

**3. Frontend Setup:**

```bash
cd frontend

# Install dependencies
npm install
cd ..
```
