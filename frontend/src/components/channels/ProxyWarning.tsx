/**
 * 代理警告组件
 * 显示代理检测结果和针对性指导
 * Task 18.3 - Requirements 1.3, 7.6
 */
import React from 'react';
import { Alert, AlertDescription, AlertTitle } from '../ui/alert';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  AlertTriangle,
  CheckCircle,
  Info,
  ExternalLink,
  Settings,
  Shield,
} from 'lucide-react';
import {
  ProxyInfo,
  ProxyType,
  ProxyMode,
  getProxyTypeText,
  getProxyModeText,
} from '../../types/channels';

interface ProxyWarningProps {
  proxyInfo: ProxyInfo | null;
  isLoading?: boolean;
  onSwitchMode?: () => void;
  onOpenSettings?: () => void;
}

/**
 * 获取代理软件的配置指导
 */
function getProxyGuidance(proxyType: ProxyType, proxyMode: ProxyMode): {
  title: string;
  description: string;
  steps: string[];
  severity: 'warning' | 'info' | 'success';
} {
  // TUN模式警告
  if (proxyMode === 'tun') {
    const guidance: Record<ProxyType, { steps: string[] }> = {
      clash: {
        steps: [
          '打开 Clash 设置',
          '关闭 TUN 模式',
          '启用系统代理模式',
          '或在规则中将微信设为直连',
        ],
      },
      clash_verge: {
        steps: [
          '打开 Clash Verge 设置',
          '进入「系统代理」选项',
          '关闭「TUN 模式」',
          '启用「系统代理」',
        ],
      },
      clash_meta: {
        steps: [
          '编辑 Clash Meta 配置文件',
          '将 tun.enable 设为 false',
          '重启 Clash Meta',
        ],
      },
      surge: {
        steps: [
          '打开 Surge 设置',
          '关闭「增强模式」',
          '使用「系统代理」模式',
        ],
      },
      v2ray: {
        steps: [
          '检查 V2Ray 配置',
          '确保未使用 TUN 模式',
          '使用系统代理或 SOCKS5 代理',
        ],
      },
      shadowsocks: {
        steps: [
          '检查 Shadowsocks 设置',
          '使用系统代理模式',
        ],
      },
      other: {
        steps: [
          '关闭代理软件的 TUN/VPN 模式',
          '切换到系统代理模式',
          '或将微信添加到直连规则',
        ],
      },
      none: { steps: [] },
    };

    return {
      title: '检测到 TUN 模式',
      description: `${getProxyTypeText(proxyType)} 正在使用 TUN 模式，这可能导致流量捕获失败。`,
      steps: guidance[proxyType]?.steps || guidance.other.steps,
      severity: 'warning',
    };
  }

  // Fake-IP模式提示
  if (proxyMode === 'fake_ip') {
    return {
      title: '检测到 Fake-IP 模式',
      description: '系统将使用 IP 识别替代方案，可能影响检测准确性。',
      steps: [
        '建议关闭 Fake-IP 模式以获得更好的检测效果',
        '或者继续使用，系统会自动切换到 IP 识别模式',
      ],
      severity: 'info',
    };
  }

  // 系统代理模式 - 正常
  if (proxyMode === 'system_proxy') {
    return {
      title: '代理配置正常',
      description: `${getProxyTypeText(proxyType)} 使用系统代理模式，与捕获功能兼容。`,
      steps: [],
      severity: 'success',
    };
  }

  // 无代理
  if (proxyType === 'none') {
    return {
      title: '未检测到代理',
      description: '系统将使用 WinDivert 透明捕获模式。',
      steps: [],
      severity: 'success',
    };
  }

  // 其他情况
  return {
    title: `检测到 ${getProxyTypeText(proxyType)}`,
    description: `当前模式: ${getProxyModeText(proxyMode)}`,
    steps: [],
    severity: 'info',
  };
}

/**
 * 代理警告组件
 */
export const ProxyWarning: React.FC<ProxyWarningProps> = ({
  proxyInfo,
  isLoading = false,
  onSwitchMode,
  onOpenSettings,
}) => {
  if (isLoading) {
    return (
      <Alert>
        <Info className="h-4 w-4" />
        <AlertTitle>正在检测代理...</AlertTitle>
        <AlertDescription>
          正在扫描系统中运行的代理软件
        </AlertDescription>
      </Alert>
    );
  }

  if (!proxyInfo) {
    return null;
  }

  const guidance = getProxyGuidance(proxyInfo.proxy_type, proxyInfo.proxy_mode);

  // 成功状态 - 简化显示
  if (guidance.severity === 'success') {
    return (
      <Alert className="border-green-500/50 bg-green-50 dark:bg-green-950/20">
        <CheckCircle className="h-4 w-4 text-green-600" />
        <AlertTitle className="text-green-800 dark:text-green-200">
          {guidance.title}
        </AlertTitle>
        <AlertDescription className="text-green-700 dark:text-green-300">
          {guidance.description}
        </AlertDescription>
      </Alert>
    );
  }

  // 警告或信息状态
  const isWarning = guidance.severity === 'warning';
  const Icon = isWarning ? AlertTriangle : Info;
  const alertClass = isWarning
    ? 'border-yellow-500/50 bg-yellow-50 dark:bg-yellow-950/20'
    : 'border-blue-500/50 bg-blue-50 dark:bg-blue-950/20';
  const titleClass = isWarning
    ? 'text-yellow-800 dark:text-yellow-200'
    : 'text-blue-800 dark:text-blue-200';
  const textClass = isWarning
    ? 'text-yellow-700 dark:text-yellow-300'
    : 'text-blue-700 dark:text-blue-300';

  return (
    <Alert className={alertClass}>
      <Icon className={`h-4 w-4 ${isWarning ? 'text-yellow-600' : 'text-blue-600'}`} />
      <AlertTitle className={titleClass}>
        <div className="flex items-center gap-2">
          {guidance.title}
          {proxyInfo.process_name && (
            <Badge variant="outline" className="text-xs">
              {proxyInfo.process_name}
            </Badge>
          )}
        </div>
      </AlertTitle>
      <AlertDescription className={textClass}>
        <div className="space-y-3">
          <p>{guidance.description}</p>

          {/* 配置步骤 */}
          {guidance.steps.length > 0 && (
            <div className="space-y-1">
              <p className="font-medium">建议操作：</p>
              <ol className="list-decimal list-inside space-y-1 text-sm">
                {guidance.steps.map((step, index) => (
                  <li key={index}>{step}</li>
                ))}
              </ol>
            </div>
          )}

          {/* 额外信息 */}
          <div className="flex flex-wrap gap-2 pt-2">
            {proxyInfo.is_tun_enabled && (
              <Badge variant="secondary" className="text-xs">
                <Shield className="h-3 w-3 mr-1" />
                TUN 已启用
              </Badge>
            )}
            {proxyInfo.is_fake_ip_enabled && (
              <Badge variant="secondary" className="text-xs">
                Fake-IP 已启用
              </Badge>
            )}
            {proxyInfo.api_address && (
              <Badge variant="outline" className="text-xs font-mono">
                API: {proxyInfo.api_address}
              </Badge>
            )}
          </div>

          {/* 操作按钮 */}
          {(onSwitchMode || onOpenSettings) && (
            <div className="flex gap-2 pt-2">
              {onSwitchMode && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onSwitchMode}
                  className="text-xs"
                >
                  <Settings className="h-3 w-3 mr-1" />
                  切换捕获模式
                </Button>
              )}
              {onOpenSettings && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onOpenSettings}
                  className="text-xs"
                >
                  <ExternalLink className="h-3 w-3 mr-1" />
                  打开代理设置
                </Button>
              )}
            </div>
          )}
        </div>
      </AlertDescription>
    </Alert>
  );
};

export default ProxyWarning;
