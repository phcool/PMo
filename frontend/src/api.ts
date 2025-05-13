// Chat API methods
export function createChatSession(paperId = null) {
  const url = paperId 
    ? `${baseUrl}/chat/create_session?paper_id=${paperId}` 
    : `${baseUrl}/chat/create_session`;
  
  return axios.post(url);
}

export function sendChatMessage(chatId, message, paperId = null) {
  const url = `${baseUrl}/chat/${chatId}/send_message`;
  
  return axios.post(url, {
    message,
    paper_id: paperId
  });
}

export function uploadPdf(formData, chatId = null) {
  const url = chatId 
    ? `${baseUrl}/chat/${chatId}/upload_pdf` 
    : `${baseUrl}/upload_pdf`;
  
  return axios.post(url, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
}

export function checkPdfProcessingStatus(jobId) {
  return axios.get(`${baseUrl}/pdf/processing_status/${jobId}`);
}

export function removePdfFromChat(chatId, fileName) {
  return axios.delete(`${baseUrl}/chat/${chatId}/pdf/${encodeURIComponent(fileName)}`);
}

export default {
  createChatSession,
  sendChatMessage,
  uploadPdf,
  checkPdfProcessingStatus,
  removePdfFromChat
}; 