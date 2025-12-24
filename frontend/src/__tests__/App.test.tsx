/**
 * App 组件测试
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import packageJson from '../../package.json';
import App from '../App';

describe('App Component', () => {
  it('renders without crashing', () => {
    render(<App />);
    expect(screen.getByText(/VidFlow Desktop/i)).toBeInTheDocument();
  });

  it('displays the correct version', () => {
    render(<App />);
    const escapedVersion = packageJson.version.replace(/\./g, '\\.')
    const versionRegex = new RegExp(`v\\s*${escapedVersion}`);
    expect(screen.getByText(versionRegex)).toBeInTheDocument();
  });

  it('shows navigation items', () => {
    render(<App />);
    
    // 检查导航项是否存在
    expect(screen.getByText('下载中心')).toBeInTheDocument();
    expect(screen.getByText('任务管理')).toBeInTheDocument();
    expect(screen.getByText('字幕处理')).toBeInTheDocument();
    expect(screen.getByText('烧录字幕')).toBeInTheDocument();
    expect(screen.getByText('日志中心')).toBeInTheDocument();
    expect(screen.getByText('系统设置')).toBeInTheDocument();
  });

  it('renders main layout', () => {
    render(<App />);
    // 检查主容器是否渲染
    const mainContainer = document.querySelector('.h-screen.bg-background');
    expect(mainContainer).toBeInTheDocument();
  });
});
