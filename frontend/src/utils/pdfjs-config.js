// Check if PDF.js library already exists
let pdfLibPromise = null;

function initPdfLib() {
  if (pdfLibPromise) {
    return pdfLibPromise;
  }
  
  pdfLibPromise = new Promise((resolve) => {
    // If already loaded, return directly
    if (window.pdfjsLib) {
      resolve(window.pdfjsLib);
      return;
    }

    // Check if PDF.js is already loaded
    function checkPdfjs() {
      if (window.pdfjsLib) {
        resolve(window.pdfjsLib);
      } else {
        // Continue waiting
        setTimeout(checkPdfjs, 100);
      }
    }
    
    checkPdfjs();
  });
  
  return pdfLibPromise;
}

// Export an async function to get the PDF.js library
export default function getPdfLib() {
  return initPdfLib();
} 