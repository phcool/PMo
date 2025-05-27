export interface Paper {
  paper_id: string;
  
  title: string;
  
  authors: string[];
  
  abstract: string;
  
  categories: string[];
  
  pdf_url: string;
  
  published_date: string;
  
  updated_date?: string;
}

