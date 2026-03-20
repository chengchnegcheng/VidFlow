import { useEffect, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Copy, Scissors, Clipboard, RotateCcw, RotateCw, Trash2, CheckSquare } from 'lucide-react';

interface MenuItem {
  label: string;
  icon?: React.ReactNode;
  action: () => void;
  disabled?: boolean;
  separator?: boolean;
}

interface ContextMenuProps {
  x: number;
  y: number;
  isEditable: boolean;
  hasSelection: boolean;
  onClose: () => void;
}

function ContextMenuContent({ x, y, isEditable, hasSelection, onClose }: ContextMenuProps) {
  const [position, setPosition] = useState({ x, y });

  useEffect(() => {
    // 确保菜单不超出屏幕
    const menuWidth = 160;
    const menuHeight = isEditable ? 280 : 100;

    let newX = x;
    let newY = y;

    if (x + menuWidth > window.innerWidth) {
      newX = window.innerWidth - menuWidth - 10;
    }
    if (y + menuHeight > window.innerHeight) {
      newY = window.innerHeight - menuHeight - 10;
    }

    setPosition({ x: newX, y: newY });
  }, [x, y, isEditable]);

  const handleAction = useCallback((action: () => void) => {
    action();
    onClose();
  }, [onClose]);

  const execCommand = useCallback((command: string) => {
    document.execCommand(command);
  }, []);

  const menuItems: MenuItem[] = isEditable
    ? [
        {
          label: '撤销',
          icon: <RotateCcw className="size-4" />,
          action: () => execCommand('undo'),
        },
        {
          label: '重做',
          icon: <RotateCw className="size-4" />,
          action: () => execCommand('redo'),
        },
        { label: '', action: () => {}, separator: true },
        {
          label: '剪切',
          icon: <Scissors className="size-4" />,
          action: () => execCommand('cut'),
          disabled: !hasSelection,
        },
        {
          label: '复制',
          icon: <Copy className="size-4" />,
          action: () => execCommand('copy'),
          disabled: !hasSelection,
        },
        {
          label: '粘贴',
          icon: <Clipboard className="size-4" />,
          action: () => execCommand('paste'),
        },
        {
          label: '删除',
          icon: <Trash2 className="size-4" />,
          action: () => execCommand('delete'),
          disabled: !hasSelection,
        },
        { label: '', action: () => {}, separator: true },
        {
          label: '全选',
          icon: <CheckSquare className="size-4" />,
          action: () => execCommand('selectAll'),
        },
      ]
    : [
        {
          label: '复制',
          icon: <Copy className="size-4" />,
          action: () => execCommand('copy'),
          disabled: !hasSelection,
        },
        { label: '', action: () => {}, separator: true },
        {
          label: '全选',
          icon: <CheckSquare className="size-4" />,
          action: () => execCommand('selectAll'),
        },
      ];

  return (
    <div
      className="fixed z-[9999] min-w-[160px] rounded-lg border border-border bg-popover p-1 shadow-lg animate-in fade-in-0 zoom-in-95"
      style={{ left: position.x, top: position.y }}
      onClick={(e) => e.stopPropagation()}
    >
      {menuItems.map((item, index) =>
        item.separator ? (
          <div key={index} className="my-1 h-px bg-border" />
        ) : (
          <button
            key={index}
            className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors
              ${item.disabled
                ? 'text-muted-foreground cursor-not-allowed opacity-50'
                : 'hover:bg-accent hover:text-accent-foreground cursor-default'
              }`}
            onClick={() => !item.disabled && handleAction(item.action)}
            disabled={item.disabled}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        )
      )}
    </div>
  );
}

export function ContextMenuProvider({ children }: { children: React.ReactNode }) {
  const [menu, setMenu] = useState<{
    x: number;
    y: number;
    isEditable: boolean;
    hasSelection: boolean;
  } | null>(null);

  useEffect(() => {
    const handleContextMenu = (e: MouseEvent) => {
      e.preventDefault();

      const target = e.target as HTMLElement;
      const isEditable =
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable;

      const selection = window.getSelection();
      const hasSelection = selection ? selection.toString().length > 0 : false;

      setMenu({
        x: e.clientX,
        y: e.clientY,
        isEditable,
        hasSelection,
      });
    };

    const handleClick = () => {
      setMenu(null);
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setMenu(null);
      }
    };

    document.addEventListener('contextmenu', handleContextMenu);
    document.addEventListener('click', handleClick);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('contextmenu', handleContextMenu);
      document.removeEventListener('click', handleClick);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  return (
    <>
      {children}
      {menu &&
        createPortal(
          <ContextMenuContent
            x={menu.x}
            y={menu.y}
            isEditable={menu.isEditable}
            hasSelection={menu.hasSelection}
            onClose={() => setMenu(null)}
          />,
          document.body
        )}
    </>
  );
}
