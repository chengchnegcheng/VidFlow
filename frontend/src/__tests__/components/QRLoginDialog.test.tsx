/**
 * QR登录弹窗组件测试
 * Property 3: Status Message Consistency
 * Validates: Requirements 6.1, 6.3
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QRLoginDialog } from '../../components/QRLoginDialog';
import { QRLoginState, QRLoginStatus, getStatusMessage, STATUS_MESSAGES } from '../../types/qr-login';

/**
 * 创建测试状态
 */
const createTestState = (overrides: Partial<QRLoginState> = {}): QRLoginState => ({
  isOpen: true,
  platform: 'bilibili',
  platformNameZh: '哔哩哔哩',
  status: 'waiting',
  message: '请使用 哔哩哔哩 APP 扫描二维码',
  qrcodeUrl: 'https://example.com/qr.png',
  qrcodeKey: 'test-key',
  expiresIn: 180,
  pollingInterval: null,
  ...overrides,
});

describe('QRLoginDialog Component', () => {
  describe('Property 3: Status Message Consistency', () => {
    /**
     * Property 3.1: LOADING 状态消息
     * LOADING → "正在获取二维码..."
     */
    it('should display correct message for LOADING status', () => {
      const state = createTestState({
        status: 'loading',
        message: getStatusMessage('loading'),
        qrcodeUrl: null,
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={vi.fn()}
          isTerminalStatus={false}
        />
      );

      // 使用 getAllByText 因为消息会在多处显示
      const elements = screen.getAllByText('正在获取二维码...');
      expect(elements.length).toBeGreaterThan(0);
    });

    /**
     * Property 3.2: WAITING 状态消息
     * WAITING → "请使用 [平台名] APP 扫描二维码"
     */
    it('should display correct message for WAITING status with platform name', () => {
      const platformName = '哔哩哔哩';
      const state = createTestState({
        status: 'waiting',
        platformNameZh: platformName,
        message: getStatusMessage('waiting', platformName),
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={vi.fn()}
          isTerminalStatus={false}
        />
      );

      expect(screen.getByText(`请使用 ${platformName} 扫描二维码`)).toBeInTheDocument();
    });

    /**
     * Property 3.3: SCANNED 状态消息
     * SCANNED → "已扫码，请在手机上确认登录"
     */
    it('should display correct message for SCANNED status', () => {
      const state = createTestState({
        status: 'scanned',
        message: getStatusMessage('scanned'),
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={vi.fn()}
          isTerminalStatus={false}
        />
      );

      expect(screen.getByText('已扫码，请在手机上确认登录')).toBeInTheDocument();
    });

    /**
     * Property 3.4: SUCCESS 状态消息
     * SUCCESS → "[平台名] Cookie 获取成功并已保存"
     */
    it('should display correct message for SUCCESS status with platform name', () => {
      const platformName = '抖音';
      const state = createTestState({
        status: 'success',
        platformNameZh: platformName,
        message: getStatusMessage('success', platformName),
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={vi.fn()}
          isTerminalStatus={true}
        />
      );

      expect(screen.getByText(`${platformName} Cookie 获取成功并已保存`)).toBeInTheDocument();
    });

    /**
     * Property 3.5: EXPIRED 状态消息
     * EXPIRED → "二维码已过期，请重新获取"
     */
    it('should display correct message for EXPIRED status', () => {
      const state = createTestState({
        status: 'expired',
        message: getStatusMessage('expired'),
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={vi.fn()}
          isTerminalStatus={true}
        />
      );

      expect(screen.getByText('二维码已过期，请重新获取')).toBeInTheDocument();
    });

    /**
     * Property 3.6: ERROR 状态消息
     * ERROR → "网络请求失败: [错误信息]"
     */
    it('should display correct message for ERROR status with error details', () => {
      const errorMessage = '连接超时';
      const state = createTestState({
        status: 'error',
        message: getStatusMessage('error', undefined, errorMessage),
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={vi.fn()}
          isTerminalStatus={true}
        />
      );

      expect(screen.getByText(`网络请求失败: ${errorMessage}`)).toBeInTheDocument();
    });

    /**
     * Property 3.7: 所有状态消息函数正确性
     * 验证 STATUS_MESSAGES 映射的完整性
     */
    it('should have correct status message mappings for all statuses', () => {
      const allStatuses: QRLoginStatus[] = ['loading', 'waiting', 'scanned', 'success', 'expired', 'error'];
      const platformName = '测试平台';

      allStatuses.forEach(status => {
        expect(STATUS_MESSAGES[status]).toBeDefined();
        const message = STATUS_MESSAGES[status](platformName);
        expect(typeof message).toBe('string');
        expect(message.length).toBeGreaterThan(0);
      });
    });

    /**
     * Property 3.8: 状态消息中文显示
     * 所有状态消息应为中文
     */
    it('should display all status messages in Chinese', () => {
      const chineseCharRegex = /[\u4e00-\u9fa5]/;
      const allStatuses: QRLoginStatus[] = ['loading', 'waiting', 'scanned', 'success', 'expired', 'error'];

      allStatuses.forEach(status => {
        const message = STATUS_MESSAGES[status]('测试平台');
        expect(chineseCharRegex.test(message)).toBe(true);
      });
    });
  });

  describe('UI Interactions', () => {
    /**
     * 测试关闭按钮
     */
    it('should call onClose when close button is clicked', () => {
      const onClose = vi.fn();
      const state = createTestState();

      render(
        <QRLoginDialog
          state={state}
          onClose={onClose}
          onRefresh={vi.fn()}
          isTerminalStatus={false}
        />
      );

      fireEvent.click(screen.getByText('关闭'));
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    /**
     * 测试刷新按钮（等待状态）
     */
    it('should call onRefresh when refresh button is clicked in waiting status', () => {
      const onRefresh = vi.fn();
      const state = createTestState({ status: 'waiting' });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={onRefresh}
          isTerminalStatus={false}
        />
      );

      fireEvent.click(screen.getByText('刷新二维码'));
      expect(onRefresh).toHaveBeenCalledTimes(1);
    });

    /**
     * 测试刷新按钮（过期状态）
     */
    it('should call onRefresh when refresh button is clicked in expired status', () => {
      const onRefresh = vi.fn();
      const state = createTestState({
        status: 'expired',
        message: '二维码已过期，请重新获取',
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={onRefresh}
          isTerminalStatus={true}
        />
      );

      fireEvent.click(screen.getByText('重新获取二维码'));
      expect(onRefresh).toHaveBeenCalledTimes(1);
    });

    /**
     * 测试成功状态下的完成按钮
     */
    it('should show "完成" button text when status is success', () => {
      const state = createTestState({
        status: 'success',
        message: '哔哩哔哩 Cookie 获取成功并已保存',
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={vi.fn()}
          isTerminalStatus={true}
        />
      );

      expect(screen.getByText('完成')).toBeInTheDocument();
    });
  });

  describe('QR Code Display', () => {
    /**
     * 测试二维码图片显示
     */
    it('should display QR code image when qrcodeUrl is provided', () => {
      const state = createTestState({
        qrcodeUrl: 'https://example.com/qr.png',
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={vi.fn()}
          isTerminalStatus={false}
        />
      );

      const img = screen.getByAltText('登录二维码');
      expect(img).toBeInTheDocument();
      expect(img).toHaveAttribute('src', 'https://example.com/qr.png');
    });

    /**
     * 测试base64二维码显示
     */
    it('should display base64 QR code image', () => {
      const base64Url = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
      const state = createTestState({
        qrcodeUrl: base64Url,
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={vi.fn()}
          isTerminalStatus={false}
        />
      );

      const img = screen.getByAltText('登录二维码');
      expect(img).toHaveAttribute('src', base64Url);
    });

    /**
     * 测试加载状态显示
     */
    it('should show loading spinner when status is loading', () => {
      const state = createTestState({
        status: 'loading',
        qrcodeUrl: null,
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={vi.fn()}
          isTerminalStatus={false}
        />
      );

      // 检查加载提示文本
      expect(screen.getByText('正在获取二维码...')).toBeInTheDocument();
    });

    /**
     * 测试过期状态覆盖层
     */
    it('should show expired overlay when status is expired', () => {
      const state = createTestState({
        status: 'expired',
        message: '二维码已过期，请重新获取',
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={vi.fn()}
          isTerminalStatus={true}
        />
      );

      expect(screen.getByText('二维码已过期')).toBeInTheDocument();
    });

    /**
     * 测试成功状态覆盖层
     */
    it('should show success overlay when status is success', () => {
      const state = createTestState({
        status: 'success',
        message: '哔哩哔哩 Cookie 获取成功并已保存',
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={vi.fn()}
          isTerminalStatus={true}
        />
      );

      expect(screen.getByText('登录成功')).toBeInTheDocument();
    });
  });

  describe('Dialog Header', () => {
    /**
     * 测试弹窗标题显示平台名称
     */
    it('should display platform name in dialog title', () => {
      const state = createTestState({
        platformNameZh: '小红书',
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={vi.fn()}
          isTerminalStatus={false}
        />
      );

      expect(screen.getByText('小红书 扫码登录')).toBeInTheDocument();
    });

    /**
     * 测试弹窗描述
     */
    it('should display correct dialog description', () => {
      const state = createTestState({
        platformNameZh: '快手',
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={vi.fn()}
          isTerminalStatus={false}
        />
      );

      expect(screen.getByText('使用 快手 APP 扫描下方二维码完成登录')).toBeInTheDocument();
    });
  });

  describe('Scan Instructions', () => {
    /**
     * 测试等待状态下的扫码提示
     */
    it('should show scan instructions when status is waiting', () => {
      const state = createTestState({
        status: 'waiting',
        platformNameZh: '微博',
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={vi.fn()}
          isTerminalStatus={false}
        />
      );

      expect(screen.getByText('1. 打开 微博 APP')).toBeInTheDocument();
      expect(screen.getByText('2. 扫描上方二维码')).toBeInTheDocument();
      expect(screen.getByText('3. 在手机上确认登录')).toBeInTheDocument();
    });

    /**
     * 测试已扫码状态下的确认提示
     */
    it('should show confirmation prompt when status is scanned', () => {
      const state = createTestState({
        status: 'scanned',
      });

      render(
        <QRLoginDialog
          state={state}
          onClose={vi.fn()}
          onRefresh={vi.fn()}
          isTerminalStatus={false}
        />
      );

      expect(screen.getByText('请在手机上点击确认登录')).toBeInTheDocument();
    });
  });
});
