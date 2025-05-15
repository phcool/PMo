# DL Paper Monitor - Frontend

A web application for monitoring deep learning research papers, providing search, analysis, chat, and PDF viewing capabilities.

## Tech Stack

- **Vue 3**: Progressive JavaScript framework for building user interfaces
- **TypeScript**: Adds static typing to enhance developer experience and code quality
- **Vite**: Fast and modern build tool and development server
- **Vue Router**: Official router for Vue.js
- **Axios**: Promise-based HTTP client for browser and Node.js
- **Marked + DOMPurify**: Markdown parsing and sanitization
- **Vue Toastification**: Toast notifications for Vue
- **PDF.js**: For PDF rendering capabilities

## Project Structure

```
frontend/
├── dist/               # Built files (not committed)
├── public/             # Static files that will be copied to build output
│   └── pdfjs/          # PDF.js library files
├── src/
│   ├── assets/         # Static assets (images, fonts, etc.)
│   ├── components/     # Reusable Vue components
│   ├── router/         # Vue Router configuration
│   ├── services/       # API and other service classes
│   ├── types/          # TypeScript type definitions
│   ├── utils/          # Utility functions
│   ├── views/          # Page components
│   ├── App.vue         # Root component
│   ├── env.d.ts        # TypeScript declarations
│   └── main.ts         # Application entry point
├── .env                # Environment variables
├── index.html          # HTML template
├── package.json        # Project dependencies and scripts
├── tsconfig.json       # TypeScript configuration
├── tsconfig.node.json  # TypeScript configuration for Node.js
└── vite.config.ts      # Vite configuration
```

## Setup and Development

### Prerequisites

- Node.js (v16+)
- npm (v7+)

### Installation

```bash
# Install dependencies
npm install
```

### Development

```bash
# Start development server
npm run dev
```

### Building for Production

```bash
# Build the application
npm run build

# Preview the built application
npm run preview
```

## Code Style and Guidelines

- Use TypeScript for all new files
- Follow Vue 3 Composition API patterns
- Use proper interfaces for API responses
- Properly document code with JSDoc comments
- Follow the principle of single responsibility
- Implement error handling for all API calls

## API Integration

The frontend communicates with the backend API for data retrieval and manipulation. See the `services/api.ts` file for all available API endpoints and how to use them.

## Contribution Guidelines

1. Use descriptive branch names (feature/xxx, fix/xxx)
2. Write clear commit messages
3. Add comprehensive tests for new features
4. Update documentation when making changes
5. Follow the existing code style and patterns 