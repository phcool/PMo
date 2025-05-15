/**
 * Paper interface represents a research paper from arXiv or other sources
 */
export interface Paper {
  /** Unique identifier for the paper */
  paper_id: string;
  
  /** The title of the paper */
  title: string;
  
  /** List of authors of the paper */
  authors: string[];
  
  /** Abstract or summary of the paper content */
  abstract: string;
  
  /** Research categories or topics the paper belongs to */
  categories: string[];
  
  /** URL to the PDF file */
  pdf_url: string;
  
  /** Date when the paper was first published */
  published_date: string;
  
  /** Date when the paper was last updated (optional) */
  updated_date?: string;
}

/**
 * Search request parameters for paper search
 */
export interface SearchRequest {
  /** Search query string */
  query: string;
  
  /** Maximum number of results to return (optional) */
  limit?: number;
  
  /** Filter results by categories (optional) */
  categories?: string[];
}

/**
 * Search response format for paper search results
 */
export interface SearchResponse {
  /** Array of papers matching the search criteria */
  results: Paper[];
  
  /** Total number of matching papers */
  count: number;
}

/**
 * Category label mappings from short codes to readable names
 */
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
};

/**
 * Get a human-readable category name from a category code
 * @param category - The category code (e.g., 'cs.AI')
 * @returns The readable category name or the original code if not found
 */
export const getCategoryLabel = (category: string): string => {
  return CATEGORY_LABELS[category] || category;
}; 