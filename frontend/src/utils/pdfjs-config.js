// 检查是否已有 PDF.js 库
let pdfLibPromise = null;

function initPdfLib() {
  if (pdfLibPromise) {
    return pdfLibPromise;
  }
  
  pdfLibPromise = new Promise((resolve) => {
    // 如果已经加载，直接返回
    if (window.pdfjsLib) {
      resolve(window.pdfjsLib);
      return;
    }

    // 检查 PDF.js 是否已加载
    function checkPdfjs() {
      if (window.pdfjsLib) {
        resolve(window.pdfjsLib);
      } else {
        // 继续等待
        setTimeout(checkPdfjs, 100);
      }
    }
    
    checkPdfjs();
  });
  
  return pdfLibPromise;
}

// 导出一个获取 PDF.js 库的异步函数
export default function getPdfLib() {
  return initPdfLib();
} 