
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

