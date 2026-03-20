/**
 * 视频列表组件测试
 * Validates: Requirements 2.5, 6.2, 6.3
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { VideoList } from '../../../components/channels/VideoList';
import { DetectedVideo } from '../../../types/channels';

describe('VideoList Component', () => {
  const mockOnDownload = vi.fn();
  const mockOnClearAll = vi.fn();

  const mockVideos: DetectedVideo[] = [
    {
      id: 'video-1',
      url: 'https://finder.video.qq.com/video1.mp4',
      title: '测试视频1',
      duration: 120,
      resolution: '1080p',
      filesize: 10485760,
      thumbnail: null,
      detected_at: '2026-01-11T00:00:00Z',
      encryption_type: 'none',
      decryption_key: null,
    },
    {
      id: 'video-2',
      url: 'https://finder.video.qq.com/video2.mp4',
      title: '测试视频2',
      duration: 60,
      resolution: '720p',
      filesize: 5242880,
      thumbnail: null,
      detected_at: '2026-01-11T00:01:00Z',
      encryption_type: 'xor',
      decryption_key: '123456',
    },
  ];

  const defaultProps = {
    videos: mockVideos,
    onDownload: mockOnDownload,
    onClearAll: mockOnClearAll,
  };

  beforeEach(() => {
    mockOnDownload.mockReset();
    mockOnClearAll.mockReset();
  });

  describe('Rendering', () => {
    it('should render empty state when no videos', () => {
      render(<VideoList {...defaultProps} videos={[]} />);

      expect(screen.getByText('暂无检测到的视频')).toBeInTheDocument();
    });

    it('should render video list with titles', () => {
      render(<VideoList {...defaultProps} />);

      expect(screen.getByRole('heading', { name: '测试视频1' })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: '测试视频2' })).toBeInTheDocument();
    });

    it('should display video count', () => {
      render(<VideoList {...defaultProps} />);

      expect(screen.getByText('检测到的视频 (2)')).toBeInTheDocument();
    });

    it('should display video duration', () => {
      render(<VideoList {...defaultProps} />);

      expect(screen.getByText('2:00')).toBeInTheDocument();
      expect(screen.getByText('1:00')).toBeInTheDocument();
    });

    it('should display video resolution', () => {
      render(<VideoList {...defaultProps} />);

      expect(screen.getByText('1080p')).toBeInTheDocument();
      expect(screen.getByText('720p')).toBeInTheDocument();
    });

    it('should display encryption badge for encrypted videos', () => {
      render(<VideoList {...defaultProps} />);

      expect(screen.getByText('XOR')).toBeInTheDocument();
    });

    it('should allow download when encoded video misses decode key', () => {
      render(
        <VideoList
          {...defaultProps}
          videos={[
            {
              ...mockVideos[0],
              url: 'https://finder.video.qq.com/251/20302/stodownload?encfilekey=test123',
              encryption_type: 'unknown',
              decryption_key: null,
            },
          ]}
        />
      );

      expect(screen.getByText('缺少密钥')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '下载' })).not.toBeDisabled();
    });
    it('should keep placeholder videos downloadable when url exists', () => {
      render(
        <VideoList
          {...defaultProps}
          videos={[
            {
              ...mockVideos[0],
              url: 'https://finder.video.qq.com/251/20302/stodownload?encfilekey=test123',
              encryption_type: 'unknown',
              decryption_key: null,
              is_placeholder: true,
              placeholder_message: 'metadata missing',
            },
          ]}
        />
      );

      expect(screen.getByTitle('metadata missing')).not.toBeDisabled();
    });
  });

  describe('Interactions', () => {
    it('should call onDownload when clicking download button', async () => {
      render(<VideoList {...defaultProps} />);

      const downloadButtons = screen.getAllByText('下载');
      await act(async () => {
        fireEvent.click(downloadButtons[0]);
      });

      expect(mockOnDownload).toHaveBeenCalledWith({
        url: 'https://finder.video.qq.com/video1.mp4',
        quality: 'best',
        output_path: undefined,
        auto_decrypt: false,
        decryption_key: null,
      });
    });

    it('should call onClearAll when clicking clear button', () => {
      render(<VideoList {...defaultProps} />);

      const clearButton = screen.getByText('清空列表');
      fireEvent.click(clearButton);

      expect(mockOnClearAll).toHaveBeenCalled();
    });
  });
});
