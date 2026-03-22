import React from 'react';
import { Activity, AlertTriangle, Cpu, Globe, RefreshCw, Server } from 'lucide-react';

import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { ScrollArea } from '../ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import {
  DiagnosticInfo,
  ProxyInfo,
  WeChatProcessInfo,
  formatLastDetectionTime,
  getProxyModeText,
  getProxyTypeText,
} from '../../types/channels';

interface DiagnosticsPanelProps {
  diagnostics: DiagnosticInfo | null;
  isLoading: boolean;
  onRefresh: () => Promise<void>;
}

function renderEmptyState(message: string) {
  return <div className="py-4 text-center text-muted-foreground">{message}</div>;
}

const SNIList: React.FC<{ snis: string[] }> = ({ snis }) => {
  if (snis.length === 0) {
    return renderEmptyState('暂无检测到的SNI');
  }

  return (
    <ScrollArea className="h-[200px]">
      <div className="space-y-1">
        {snis.map((sni) => (
          <div
            key={sni}
            className="flex items-center gap-2 rounded-md bg-muted/50 p-2 text-sm font-mono"
          >
            <Globe className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
            <span className="truncate">{sni}</span>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
};

const IPList: React.FC<{ ips: string[] }> = ({ ips }) => {
  if (ips.length === 0) {
    return renderEmptyState('暂无检测到的IP');
  }

  return (
    <ScrollArea className="h-[200px]">
      <div className="space-y-1">
        {ips.map((ip) => (
          <div
            key={ip}
            className="flex items-center gap-2 rounded-md bg-muted/50 p-2 text-sm font-mono"
          >
            <Server className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
            <span>{ip}</span>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
};

const ProcessList: React.FC<{ processes: WeChatProcessInfo[] }> = ({ processes }) => {
  if (processes.length === 0) {
    return renderEmptyState('未检测到微信进程');
  }

  return (
    <ScrollArea className="h-[200px]">
      <div className="space-y-2">
        {processes.map((processInfo) => (
          <div key={processInfo.pid} className="space-y-1 rounded-md bg-muted/50 p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Cpu className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">{processInfo.name}</span>
              </div>
              <Badge variant="outline">PID: {processInfo.pid}</Badge>
            </div>
            <div className="truncate text-xs text-muted-foreground">{processInfo.exe_path}</div>
            {processInfo.ports.length > 0 && (
              <div className="text-xs">
                <span className="text-muted-foreground">端口: </span>
                <span className="font-mono">{processInfo.ports.slice(0, 5).join(', ')}</span>
                {processInfo.ports.length > 5 && (
                  <span className="text-muted-foreground"> +{processInfo.ports.length - 5}</span>
                )}
              </div>
            )}
            <div className="text-xs text-muted-foreground">
              最后活动: {formatLastDetectionTime(processInfo.last_seen)}
            </div>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
};

const ProxyInfoDisplay: React.FC<{ proxyInfo: ProxyInfo | null }> = ({ proxyInfo }) => {
  if (!proxyInfo) {
    return renderEmptyState('无代理信息');
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
          <div className="text-xs text-muted-foreground">API 地址</div>
          <div className="font-mono text-sm">{proxyInfo.api_address}</div>
        </div>
      )}

      <div className="flex gap-2">
        {proxyInfo.is_tun_enabled && <Badge variant="secondary">TUN 已启用</Badge>}
        {proxyInfo.is_fake_ip_enabled && <Badge variant="secondary">Fake-IP 已启用</Badge>}
      </div>
    </div>
  );
};

const StatisticsDisplay: React.FC<{
  statistics: Record<string, boolean | number | string | null>;
}> = ({ statistics }) => {
  const entries = Object.entries(statistics).filter(([, value]) => value !== null);

  if (entries.length === 0) {
    return renderEmptyState('暂无统计数据');
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-md bg-muted/50 p-3">
          <div className="text-xs text-muted-foreground">
            {key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())}
          </div>
          <div className="text-lg font-semibold">
            {typeof value === 'number' ? value.toLocaleString() : String(value)}
          </div>
        </div>
      ))}
    </div>
  );
};

const ErrorLog: React.FC<{ errors: string[] }> = ({ errors }) => {
  if (errors.length === 0) {
    return renderEmptyState('无错误记录');
  }

  return (
    <ScrollArea className="h-[200px]">
      <div className="space-y-2">
        {errors.map((error, index) => (
          <div
            key={`${error}-${index}`}
            className="flex items-start gap-2 rounded-md bg-destructive/10 p-2 text-sm"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-destructive" />
            <span className="text-destructive">{error}</span>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
};

export const DiagnosticsPanel: React.FC<DiagnosticsPanelProps> = ({
  diagnostics,
  isLoading,
  onRefresh,
}) => {
  const [activeTab, setActiveTab] = React.useState('sni');

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Activity className="h-5 w-5" />
            诊断信息
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              void onRefresh();
            }}
            disabled={isLoading}
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="sni" className="text-xs" onClick={() => setActiveTab('sni')}>
              SNI
              {diagnostics && diagnostics.detected_snis.length > 0 && (
                <Badge variant="secondary" className="ml-1 h-4 px-1">
                  {diagnostics.detected_snis.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="ip" className="text-xs" onClick={() => setActiveTab('ip')}>
              IP
            </TabsTrigger>
            <TabsTrigger
              value="process"
              className="text-xs"
              onClick={() => setActiveTab('process')}
            >
              进程
            </TabsTrigger>
            <TabsTrigger
              value="proxy"
              className="text-xs"
              onClick={() => setActiveTab('proxy')}
            >
              代理
            </TabsTrigger>
            <TabsTrigger
              value="stats"
              className="text-xs"
              onClick={() => setActiveTab('stats')}
            >
              统计
            </TabsTrigger>
          </TabsList>

          <TabsContent value="sni" className="mt-4" forceMount>
            <SNIList snis={diagnostics?.detected_snis || []} />
          </TabsContent>

          <TabsContent value="ip" className="mt-4" forceMount>
            <IPList ips={diagnostics?.detected_ips || []} />
          </TabsContent>

          <TabsContent value="process" className="mt-4" forceMount>
            <ProcessList processes={diagnostics?.wechat_processes || []} />
          </TabsContent>

          <TabsContent value="proxy" className="mt-4" forceMount>
            <ProxyInfoDisplay proxyInfo={diagnostics?.proxy_info || null} />
          </TabsContent>

          <TabsContent value="stats" className="mt-4" forceMount>
            <StatisticsDisplay statistics={diagnostics?.statistics || {}} />
          </TabsContent>
        </Tabs>

        {diagnostics && diagnostics.recent_errors.length > 0 && (
          <div className="mt-4 border-t pt-4">
            <div className="mb-2 flex items-center gap-2">
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
