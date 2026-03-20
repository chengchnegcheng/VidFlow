/**
 * 诊断面板组件
 * 显示实时SNI/IP列表、捕获统计和错误日志
 * Task 18.2 - Requirements 7.1, 7.2, 7.4
 */
import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { ScrollArea } from '../ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import {
  RefreshCw,
  Activity,
  Globe,
  Server,
  AlertTriangle,
  Cpu,
} from 'lucide-react';
import {
  DiagnosticInfo,
  WeChatProcessInfo,
  ProxyInfo,
  getProxyTypeText,
  getProxyModeText,
  formatLastDetectionTime,
} from '../../types/channels';

interface DiagnosticsPanelProps {
  diagnostics: DiagnosticInfo | null;
  isLoading: boolean;
  onRefresh: () => Promise<void>;
}

/**
 * SNI列表组件
 */
const SNIList: React.FC<{ snis: string[] }> = ({ snis }) => {
  if (snis.length === 0) {
    return (
      <div className="text-center text-muted-foreground py-4">
        暂无检测到的SNI
      </div>
    );
  }

  return (
    <ScrollArea className="h-[200px]">
      <div className="space-y-1">
        {snis.map((sni, index) => (
          <div
            key={index}
            className="flex items-center gap-2 p-2 rounded-md bg-muted/50 text-sm font-mono"
          >
            <Globe className="h-3 w-3 text-muted-foreground flex-shrink-0" />
            <span className="truncate">{sni}</span>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
};

/**
 * IP列表组件
 */
const IPList: React.FC<{ ips: string[] }> = ({ ips }) => {
  if (ips.length === 0) {
    return (
      <div className="text-center text-muted-foreground py-4">
        暂无检测到的IP
      </div>
    );
  }

  return (
    <ScrollArea className="h-[200px]">
      <div className="space-y-1">
        {ips.map((ip, index) => (
          <div
            key={index}
            className="flex items-center gap-2 p-2 rounded-md bg-muted/50 text-sm font-mono"
          >
            <Server className="h-3 w-3 text-muted-foreground flex-shrink-0" />
            <span>{ip}</span>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
};

/**
 * 微信进程列表组件
 */
const ProcessList: React.FC<{ processes: WeChatProcessInfo[] }> = ({ processes }) => {
  if (processes.length === 0) {
    return (
      <div className="text-center text-muted-foreground py-4">
        未检测到微信进程
      </div>
    );
  }

  return (
    <ScrollArea className="h-[200px]">
      <div className="space-y-2">
        {processes.map((proc) => (
          <div
            key={proc.pid}
            className="p-3 rounded-md bg-muted/50 space-y-1"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Cpu className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">{proc.name}</span>
              </div>
              <Badge variant="outline">PID: {proc.pid}</Badge>
            </div>
            <div className="text-xs text-muted-foreground truncate">
              {proc.exe_path}
            </div>
            {proc.ports.length > 0 && (
              <div className="text-xs">
                <span className="text-muted-foreground">端口: </span>
                <span className="font-mono">{proc.ports.slice(0, 5).join(', ')}</span>
                {proc.ports.length > 5 && <span className="text-muted-foreground"> +{proc.ports.length - 5}</span>}
              </div>
            )}
            <div className="text-xs text-muted-foreground">
              最后活动: {formatLastDetectionTime(proc.last_seen)}
            </div>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
};

/**
 * 代理信息组件
 */
const ProxyInfoDisplay: React.FC<{ proxyInfo: ProxyInfo | null }> = ({ proxyInfo }) => {
  if (!proxyInfo) {
    return (
      <div className="text-center text-muted-foreground py-4">
        无代理信息
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs text-muted-foreground">代理类型</div>
          <div className="font-medium">{getProxyTypeText(proxyInfo.proxy_type)}</div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">工作模式</div>
          <div className="font-medium">{getProxyModeText(proxyInfo.proxy_mode)}</div>
        </div>
      </div>
      
      {proxyInfo.process_name && (
        <div>
          <div className="text-xs text-muted-foreground">进程名</div>
          <div className="font-mono text-sm">{proxyInfo.process_name}</div>
        </div>
      )}
      
      {proxyInfo.api_address && (
        <div>
          <div className="text-xs text-muted-foreground">API地址</div>
          <div className="font-mono text-sm">{proxyInfo.api_address}</div>
        </div>
      )}
      
      <div className="flex gap-2">
        {proxyInfo.is_tun_enabled && (
          <Badge variant="secondary">TUN已启用</Badge>
        )}
        {proxyInfo.is_fake_ip_enabled && (
          <Badge variant="secondary">Fake-IP已启用</Badge>
        )}
      </div>
    </div>
  );
};

/**
 * 统计信息组件
 */
const StatisticsDisplay: React.FC<{ statistics: Record<string, boolean | number | string | null> }> = ({ statistics }) => {
  const entries = Object.entries(statistics).filter(([_, v]) => v !== null);
  
  if (entries.length === 0) {
    return (
      <div className="text-center text-muted-foreground py-4">
        暂无统计数据
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      {entries.map(([key, value]) => (
        <div key={key} className="p-3 rounded-md bg-muted/50">
          <div className="text-xs text-muted-foreground">
            {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
          </div>
          <div className="text-lg font-semibold">
            {typeof value === 'number' ? value.toLocaleString() : value}
          </div>
        </div>
      ))}
    </div>
  );
};

/**
 * 错误日志组件
 */
const ErrorLog: React.FC<{ errors: string[] }> = ({ errors }) => {
  if (errors.length === 0) {
    return (
      <div className="text-center text-muted-foreground py-4">
        无错误记录
      </div>
    );
  }

  return (
    <ScrollArea className="h-[200px]">
      <div className="space-y-2">
        {errors.map((error, index) => (
          <div
            key={index}
            className="flex items-start gap-2 p-2 rounded-md bg-destructive/10 text-sm"
          >
            <AlertTriangle className="h-4 w-4 text-destructive flex-shrink-0 mt-0.5" />
            <span className="text-destructive">{error}</span>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
};

/**
 * 诊断面板组件
 */
export const DiagnosticsPanel: React.FC<DiagnosticsPanelProps> = ({
  diagnostics,
  isLoading,
  onRefresh,
}) => {
  const [activeTab, setActiveTab] = useState('sni');

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Activity className="h-5 w-5" />
            诊断信息
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={onRefresh}
            disabled={isLoading}
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="sni" className="text-xs">
              SNI
              {diagnostics && diagnostics.detected_snis.length > 0 && (
                <Badge variant="secondary" className="ml-1 h-4 px-1">
                  {diagnostics.detected_snis.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="ip" className="text-xs">IP</TabsTrigger>
            <TabsTrigger value="process" className="text-xs">进程</TabsTrigger>
            <TabsTrigger value="proxy" className="text-xs">代理</TabsTrigger>
            <TabsTrigger value="stats" className="text-xs">统计</TabsTrigger>
          </TabsList>

          <TabsContent value="sni" className="mt-4">
            <SNIList snis={diagnostics?.detected_snis || []} />
          </TabsContent>

          <TabsContent value="ip" className="mt-4">
            <IPList ips={diagnostics?.detected_ips || []} />
          </TabsContent>

          <TabsContent value="process" className="mt-4">
            <ProcessList processes={diagnostics?.wechat_processes || []} />
          </TabsContent>

          <TabsContent value="proxy" className="mt-4">
            <ProxyInfoDisplay proxyInfo={diagnostics?.proxy_info || null} />
          </TabsContent>

          <TabsContent value="stats" className="mt-4">
            <StatisticsDisplay statistics={diagnostics?.statistics || {}} />
          </TabsContent>
        </Tabs>

        {/* 错误日志（如果有） */}
        {diagnostics && diagnostics.recent_errors.length > 0 && (
          <div className="mt-4 pt-4 border-t">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-4 w-4 text-destructive" />
              <span className="text-sm font-medium">最近错误</span>
            </div>
            <ErrorLog errors={diagnostics.recent_errors} />
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default DiagnosticsPanel;
