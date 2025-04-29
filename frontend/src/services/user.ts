import { v4 as uuidv4 } from 'uuid';

// 本地存储键
const USER_ID_KEY = 'dlmonitor_user_id';

/**
 * 用户服务 - 管理用户唯一标识
 */
export default {
  /**
   * 获取用户ID，如果不存在则创建一个新的
   */
  getUserId(): string {
    let userId = localStorage.getItem(USER_ID_KEY);
    
    // 如果不存在，创建一个新的用户ID
    if (!userId) {
      userId = uuidv4();
      localStorage.setItem(USER_ID_KEY, userId);
    }
    
    return userId;
  },
  
  /**
   * 检查用户ID是否已存在
   */
  hasUserId(): boolean {
    return !!localStorage.getItem(USER_ID_KEY);
  },
  
  /**
   * 重置用户ID（用于测试或重置用户状态）
   */
  resetUserId(): void {
    localStorage.removeItem(USER_ID_KEY);
  }
}; 