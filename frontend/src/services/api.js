import axios from 'axios';
import Toast from 'vue-toastification';

// API基础URL，从环境变量获取
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

// 记录论文浏览记录
async function recordPaperView(paperId) {
  try {
    const response = await axios.post(`${API_BASE_URL}/api/papers/${paperId}/view`);
    return response.data;
  } catch (error) {
    console.error('Failed to record paper view:', error);
    throw error;
  }
}

// 获取论文详情
async function getPaperById(paperId) {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/papers/${paperId}`);
    return response.data;
  } catch (error) {
    console.error('Failed to get paper details:', error);
    throw error;
  }
}

// 获取最近的论文
async function getRecentPapers(limit = 10, offset = 0) {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/papers`, {
      params: { limit, offset }
    });
    return response.data;
  } catch (error) {
    console.error('Failed to get recent papers:', error);
    throw error;
  }
}

// 获取论文总数
async function countPapers() {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/papers/count`);
    return response.data.count;
  } catch (error) {
    console.error('Failed to count papers:', error);
    throw error;
  }
}

// 获取推荐论文
async function getRecommendedPapers(limit = 10, offset = 0) {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/papers/recommend/`, {
      params: { limit, offset }
    });
    return response.data;
  } catch (error) {
    console.error('Failed to get recommended papers:', error);
    throw error;
  }
}

// 保存搜索历史
async function saveSearchHistory(query) {
  try {
    const response = await axios.post(`${API_BASE_URL}/api/user/search-history`, { query });
    return response.data;
  } catch (error) {
    console.error('Failed to save search history:', error);
    throw error;
  }
}

// 搜索论文
async function searchPapers(searchPayload) {
  try {
    const response = await axios.post(`${API_BASE_URL}/api/search`, searchPayload);
    return response.data;
  } catch (error) {
    console.error('Failed to search papers:', error);
    throw error;
  }
}

// 添加论文与聊天关联的API方法
async function associatePaperWithChat(paperId, chatId) {
  try {
    const response = await axios.post(`${API_BASE_URL}/api/chat/sessions/${chatId}/attach_paper`, {
      paper_id: paperId
    });
    return response.data;
  } catch (error) {
    console.error('Error associating paper with chat:', error);
    throw error;
  }
}

// 导出API对象
export default {
  recordPaperView,
  getPaperById,
  getRecentPapers,
  countPapers,
  getRecommendedPapers,
  saveSearchHistory,
  searchPapers,
  associatePaperWithChat
}; 