/**
 * API 工具函数测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import apiClient, { getApiBaseUrl, getBackendPort } from '../../utils/api';

// Mock window.electron
global.window = {
  ...global.window,
  electron: {
    invoke: vi.fn(),
  },
} as any;

describe('API Utils', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should have apiClient defined', () => {
    expect(apiClient).toBeDefined();
    expect(apiClient.getVideoInfo).toBeDefined();
    expect(apiClient.getTasks).toBeDefined();
  });

  it('should have getApiBaseUrl function', () => {
    // API_BASE_URL 初始为空，由 initializeBackendPort 动态设置
    expect(typeof getApiBaseUrl()).toBe('string');
  });

  it('should have getBackendPort function', () => {
    expect(getBackendPort()).toBe(null); // Initially null
  });

  describe('API Methods', () => {
    it('should have all required download methods', () => {
      expect(apiClient.getVideoInfo).toBeDefined();
      expect(apiClient.startDownload).toBeDefined();
      expect(apiClient.getTasks).toBeDefined();
      expect(apiClient.getTaskStatus).toBeDefined();
      expect(apiClient.deleteTask).toBeDefined();
      expect(apiClient.healthCheck).toBeDefined();
    });
  });
});
