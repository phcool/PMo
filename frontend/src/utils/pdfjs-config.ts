// PDF.js库类型声明
declare global {
  interface Window {
    pdfjsLib: any;
  }
}

// 处理PDF.js加载失败的事件
const PDF_LOAD_ERROR_EVENT = 'pdfjs-load-error';

// Check if PDF.js library already exists
let pdfLibPromise: Promise<any> | null = null;

/**
 * 初始化PDF.js库
 * @returns Promise resolving to PDF.js library or null if loading fails
 */
function initPdfLib(): Promise<any> {
  if (pdfLibPromise) {
    return pdfLibPromise;
  }
  
  pdfLibPromise = new Promise((resolve, reject) => {
    // 如果已加载，直接返回
    if (window.pdfjsLib) {
      resolve(window.pdfjsLib);
      return;
    }

    // 设置超时检测
    const timeout = setTimeout(() => {
      console.error('PDF.js library loading timed out');
      reject(new Error('PDF.js library loading timed out'));
      // 触发自定义事件通知应用
      window.dispatchEvent(new CustomEvent(PDF_LOAD_ERROR_EVENT));
    }, 10000);  // 10秒超时

    // 检查PDF.js是否加载
    function checkPdfjs(): void {
      if (window.pdfjsLib) {
        clearTimeout(timeout);
        resolve(window.pdfjsLib);
      } else {
        // 继续等待
        setTimeout(checkPdfjs, 200);
      }
    }
    
    checkPdfjs();
  });
  
  return pdfLibPromise;
}

/**
 * 获取PDF.js库实例
 * @returns Promise resolving to PDF.js library
 */
export default function getPdfLib(): Promise<any> {
  return initPdfLib().catch(error => {
    console.error('Failed to load PDF.js library:', error);
    return null;
  });
}

/**
 * 检查PDF.js是否可用
 * @returns Promise<boolean> 指示PDF.js是否可用
 */
export function isPdfLibAvailable(): Promise<boolean> {
  return getPdfLib().then(lib => !!lib);
}

/**
 * 添加PDF.js加载失败监听器
 * @param callback 当PDF.js加载失败时调用的回调函数 
 */
export function onPdfLibLoadError(callback: () => void): void {
  window.addEventListener(PDF_LOAD_ERROR_EVENT, callback);
}

/**
 * 移除PDF.js加载失败监听器
 * @param callback 要移除的回调函数
 */
export function offPdfLibLoadError(callback: () => void): void {
  window.removeEventListener(PDF_LOAD_ERROR_EVENT, callback);
} 