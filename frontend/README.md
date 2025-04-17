# DL Paper Monitor Frontend

This is the frontend for DL Paper Monitor, a tool for collecting and searching deep learning research papers.

## Project Setup

```sh
npm install
```

### Compile and Hot-Reload for Development

```sh
npm run dev
```

### Compile and Minify for Production

```sh
npm run build
```

## Features

- Browse recent papers from arXiv
- Search papers using semantic search (powered by FAISS on the backend)
- View paper details and download PDFs
- Filter papers by categories

## Technology Stack

- Vue.js 3
- Vue Router
- Pinia for state management
- Axios for API requests 