// Category label mappings
export const CATEGORY_LABELS = {
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
export const getCategoryLabel = (category) => {
  return CATEGORY_LABELS[category] || category;
}; 