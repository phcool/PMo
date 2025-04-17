// Paper interface represents a research paper from arXiv
export interface Paper {
  paper_id: string;
  title: string;
  authors: string[];
  abstract: string;
  categories: string[];
  pdf_url: string;
  published_date: string;
  updated_date?: string;
  analysis?: PaperAnalysis;
}

// Paper analysis interface
export interface PaperAnalysis {
  paper_id: string;
  summary?: string;
  key_findings?: string;
  contributions?: string;
  methodology?: string;
  limitations?: string;
  future_work?: string;
  created_at: string;
  updated_at: string;
}

// Search request parameters
export interface SearchRequest {
  query: string;
  limit?: number;
  categories?: string[];
}

// Search response format
export interface SearchResponse {
  results: Paper[];
  count: number;
}

// Category label mappings
export const CATEGORY_LABELS: Record<string, string> = {
  'cs.AI': 'Artificial Intelligence',
  'cs.LG': 'Machine Learning',
  'cs.CV': 'Computer Vision',
  'cs.CL': 'Computation and Language',
  'cs.NE': 'Neural and Evolutionary Computing',
  'cs.RO': 'Robotics',
  'cs.IR': 'Information Retrieval',
  'cs.MM': 'Multimedia',
  'stat.ML': 'Statistics - Machine Learning',
}

// Get readable category name
export const getCategoryLabel = (category: string): string => {
  return CATEGORY_LABELS[category] || category;
}; 