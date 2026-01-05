import React from 'react';
import { X } from 'lucide-react';

interface AboutDialogProps {
  isOpen: boolean;
  onClose: () => void;
  version: string;
}

const AboutDialog: React.FC<AboutDialogProps> = ({ isOpen, onClose, version }) => {
  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={onClose}
    >
      {/* 背景遮罩 */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
      
      {/* 对话框 */}
      <div 
        className="relative bg-background border border-border rounded-xl shadow-2xl w-[360px] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 标题栏 */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <span className="text-sm font-medium text-foreground">关于 VidFlow</span>
          <button
            onClick={onClose}
            className="p-1 rounded-md hover:bg-muted transition-colors"
          >
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>
        
        {/* 内容区域 */}
        <div className="p-6 flex flex-col items-center text-center">
          {/* Logo - 使用与标题栏一致的图标 */}
          <div className="w-20 h-20 rounded-2xl overflow-hidden shadow-lg border border-border/50 flex items-center justify-center bg-gradient-to-br from-[#2c2c2c] to-[#1a1a1a] mb-4">
            <svg width="56" height="56" viewBox="0 0 256 256" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="highlight-about" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" style={{stopColor:'#ffffff', stopOpacity:0.14}} />
                  <stop offset="35%" style={{stopColor:'#ffffff', stopOpacity:0.04}} />
                  <stop offset="100%" style={{stopColor:'#ffffff', stopOpacity:0}} />
                </linearGradient>
              </defs>
              <rect x="0" y="0" width="256" height="256" fill="url(#highlight-about)"/>
              <g transform="translate(128, 128)" fill="none" stroke="white" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="0" cy="-34" r="40" fill="white" fillOpacity="0.12" strokeWidth="14" strokeOpacity="0.95"/>
                <path d="M -12 -50 L -12 -18 L 16 -34 Z" fill="white" stroke="none"/>
                <path d="M 0 6 L 0 54" strokeWidth="20"/>
                <path d="M -34 54 L 0 86 L 34 54" strokeWidth="20"/>
                <rect x="-44" y="100" width="88" height="8" fill="white" stroke="none" rx="4" opacity="0.65"/>
              </g>
            </svg>
          </div>
          
          {/* 应用名称 */}
          <h2 className="text-xl font-bold text-foreground mb-1">VidFlow</h2>
          
          {/* 版本号 */}
          <p className="text-sm text-muted-foreground mb-4">版本 {version}</p>
          
          {/* 描述 */}
          <p className="text-sm text-muted-foreground mb-2">全能视频下载器</p>
          <p className="text-xs text-muted-foreground/70">
            支持 YouTube、Bilibili、抖音等平台
          </p>
        </div>
        
        {/* 底部 */}
        <div className="px-6 py-4 border-t border-border bg-muted/30">
          <p className="text-xs text-center text-muted-foreground">
            © 2025-2026 VidFlow. All rights reserved.
          </p>
        </div>
      </div>
    </div>
  );
};

export default AboutDialog;
