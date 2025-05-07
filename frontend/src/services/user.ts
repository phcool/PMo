import { v4 as uuidv4 } from 'uuid';

// Local storage key
const USER_ID_KEY = 'dlmonitor_user_id';

/**
 * User service - Manages user unique identifier
 */
export default {
  /**
   * Get user ID, create a new one if it doesn't exist
   */
  getUserId(): string {
    let userId = localStorage.getItem(USER_ID_KEY);
    
    // If it doesn't exist, create a new user ID
    if (!userId) {
      userId = uuidv4();
      localStorage.setItem(USER_ID_KEY, userId);
    }
    
    return userId;
  },
  
  /**
   * Check if user ID exists
   */
  hasUserId(): boolean {
    return !!localStorage.getItem(USER_ID_KEY);
  },
  
  /**
   * Reset user ID (for testing or resetting user state)
   */
  resetUserId(): void {
    localStorage.removeItem(USER_ID_KEY);
  }
}; 