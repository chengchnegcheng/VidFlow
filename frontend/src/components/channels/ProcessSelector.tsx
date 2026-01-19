/**
 * 进程选择器组件
 * 用于选择透明捕获的目标进程
 */
import React from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { X, Plus, Monitor } from 'lucide-react';

interface ProcessSelectorProps {
  selectedProcesses: string[];
  onChange: (processes: string[]) => void;
  disabled?: boolean;
}

/** 常用进程预设 */
const COMMON_PROCESSES = [
  { name: 'WeChat.exe', label: '微信' },
  { name: 'WeChatAppEx.exe', label: '微信小程序' },
  { name: 'chrome.exe', label: 'Chrome' },
  { name: 'msedge.exe', label: 'Edge' },
  { name: 'firefox.exe', label: 'Firefox' },
];

/**
 * 进程选择器组件
 */
export const ProcessSelector: React.FC<ProcessSelectorProps> = ({
  selectedProcesses,
  onChange,
  disabled = false,
}) => {
  const [inputValue, setInputValue] = React.useState('');

  /**
   * 添加进程
   */
  const handleAddProcess = (processName: string) => {
    const trimmed = processName.trim();
    if (trimmed && !selectedProcesses.includes(trimmed)) {
      onChange([...selectedProcesses, trimmed]);
    }
    setInputValue('');
  };

  /**
   * 移除进程
   */
  const handleRemoveProcess = (processName: string) => {
    onChange(selectedProcesses.filter(p => p !== processName));
  };

  /**
   * 处理输入框回车
   */
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && inputValue.trim()) {
      e.preventDefault();
      handleAddProcess(inputValue);
    }
  };

  /**
   * 获取未选中的常用进程
   */
  const availableCommonProcesses = COMMON_PROCESSES.filter(
    p => !selectedProcesses.includes(p.name)
  );

  return (
    <div className="space-y-3">
      {/* 已选进程列表 */}
      <div className="flex flex-wrap gap-2">
        {selectedProcesses.length === 0 ? (
          <p className="text-sm text-muted-foreground">未选择任何进程（将捕获所有流量）</p>
        ) : (
          selectedProcesses.map(process => (
            <Badge
              key={process}
              variant="secondary"
              className="flex items-center gap-1 pr-1"
            >
              <Monitor className="h-3 w-3" />
              {process}
              {!disabled && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-4 w-4 p-0 hover:bg-transparent"
                  onClick={() => handleRemoveProcess(process)}
                >
                  <X className="h-3 w-3" />
                </Button>
              )}
            </Badge>
          ))
        )}
      </div>

      {/* 添加进程输入框 */}
      {!disabled && (
        <div className="flex gap-2">
          <Input
            placeholder="输入进程名称，如 WeChat.exe"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1"
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleAddProcess(inputValue)}
            disabled={!inputValue.trim()}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* 常用进程快捷添加 */}
      {!disabled && availableCommonProcesses.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">快速添加：</p>
          <div className="flex flex-wrap gap-1">
            {availableCommonProcesses.map(process => (
              <Button
                key={process.name}
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={() => handleAddProcess(process.name)}
              >
                <Plus className="h-3 w-3 mr-1" />
                {process.label}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ProcessSelector;
