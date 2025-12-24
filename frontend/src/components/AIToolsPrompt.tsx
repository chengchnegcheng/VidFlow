import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './ui/alert-dialog';
import { AlertCircle, Download, Settings } from 'lucide-react';
import { Button } from './ui/button';

interface AIToolsPromptProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onInstall: () => void;
  onGoToSettings: () => void;
  installing?: boolean;
}

export function AIToolsPrompt({
  open,
  onOpenChange,
  onInstall,
  onGoToSettings,
  installing = false
}: AIToolsPromptProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-amber-500" />
            <AlertDialogTitle>AI 字幕功能未安装</AlertDialogTitle>
          </div>
          <AlertDialogDescription asChild>
            <div className="space-y-3">
              <p>
                生成字幕需要安装 <span className="font-medium">faster-whisper</span> AI 组件。
              </p>
              
              <div className="bg-blue-50 border border-blue-200 rounded-md p-3 space-y-2">
                <p className="font-medium text-blue-900 text-sm">AI 组件说明</p>
                <ul className="text-sm text-blue-800 space-y-1">
                  <li>• <span className="font-medium">CPU 版本</span>（推荐）：约 300 MB，兼容所有机器</li>
                  <li>• <span className="font-medium">GPU 版本</span>：约 1 GB，需要 NVIDIA 显卡</li>
                </ul>
                <p className="text-xs text-blue-700 mt-2">
                  💡 推荐使用 CPU 版本，体积小、兼容性好
                </p>
              </div>

              <p className="text-sm text-muted-foreground">
                您可以前往 <span className="font-medium">设置 → 工具配置</span> 进行安装。
              </p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="gap-2 sm:gap-0">
          <AlertDialogCancel disabled={installing}>稍后安装</AlertDialogCancel>
          <Button
            onClick={(e) => {
              e.preventDefault();
              onGoToSettings();
              onOpenChange(false);
            }}
            variant="outline"
            disabled={installing}
          >
            <Settings className="w-4 h-4 mr-2" />
            前往设置
          </Button>
          <AlertDialogAction
            onClick={(e) => {
              e.preventDefault();
              onInstall();
            }}
            className="bg-primary"
            disabled={installing}
          >
            <Download className="w-4 h-4 mr-2" />
            {installing ? '安装中...' : '立即安装（CPU）'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
