import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DownloadTaskList } from '../../../components/channels/DownloadTaskList';

vi.mock('../../../components/TaskThumbnail', () => ({
  TaskThumbnail: ({ title }: { title: string }) => <div data-testid="task-thumbnail">{title}</div>,
}));

describe('DownloadTaskList', () => {
  it('renders encrypted channel downloads as requiring a key', async () => {
    const onCancel = vi.fn();
    const onDelete = vi.fn();
    const onOpenFolder = vi.fn().mockResolvedValue(undefined);

    render(
      <DownloadTaskList
        tasks={[
          {
            task_id: 'channels_1',
            url: 'https://finder.video.qq.com/251/20302/stodownload?encfilekey=abc123',
            title: '测试视频',
            status: 'encrypted',
            progress: 100,
            speed: 0,
            downloaded: 893344,
            total: 893344,
            file_path: 'D:/downloads/test.mp4.encrypted',
            error: 'Video payload is still encrypted.',
            created_at: 1710000000,
          },
        ]}
        onCancel={onCancel}
        onDelete={onDelete}
        onOpenFolder={onOpenFolder}
      />
    );

    expect(screen.getByText('需密钥')).toBeInTheDocument();
    expect(screen.getByText('Video payload is still encrypted.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '打开文件夹' }));

    expect(onOpenFolder).toHaveBeenCalledWith('D:/downloads/test.mp4.encrypted');
  });

  it('renders an empty state when there are no tasks', () => {
    render(
      <DownloadTaskList
        tasks={[]}
        onCancel={vi.fn()}
        onDelete={vi.fn()}
        onOpenFolder={vi.fn()}
      />
    );

    expect(screen.getByText('暂无下载任务')).toBeInTheDocument();
  });
});
