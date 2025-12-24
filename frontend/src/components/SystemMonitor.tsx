import { useState, useEffect } from 'react';
import { invoke, getApiBaseUrl } from './TauriIntegration';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { Separator } from './ui/separator';
import { toast } from 'sonner';
import {
  Activity,
  Cpu,
  HardDrive,
  MemoryStick,
  Network,
  Server,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Zap,
  Database,
  FolderOpen
} from 'lucide-react';

interface SystemInfo {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  network_speed: {
    download: number;
    upload: number;
  };
  active_tasks: number;
  queue_size: number;
  total_downloads: number;
  backend_status: 'online' | 'offline';
  uptime: string;
}

export function SystemMonitor() {
  const [systemInfo, setSystemInfo] = useState<SystemInfo>({
    cpu_usage: 0,
    memory_usage: 0,
    disk_usage: 0,
    network_speed: { download: 0, upload: 0 },
    active_tasks: 0,
    queue_size: 0,
    total_downloads: 0,
    backend_status: 'online',
    uptime: '0h 0m'
  });

  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // 获取系统信息
  const fetchSystemInfo = async () => {
    try {
      const info = await invoke('get_system_info');
      if (info && typeof info === 'object') {
        setSystemInfo(info as SystemInfo);
      }
    } catch (error) {
      console.error('获取系统信息失败', error);
      toast.error('加载失败', { description: '无法获取系统信息' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSystemInfo();
    
    if (autoRefresh) {
      const interval = setInterval(fetchSystemInfo, 3000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  // 格式化网络速度
  const formatSpeed = (bytesPerSecond: number): string => {
    if (bytesPerSecond < 1024) return `${bytesPerSecond.toFixed(0)} B/s`;
    if (bytesPerSecond < 1024 * 1024) return `${(bytesPerSecond / 1024).toFixed(1)} KB/s`;
    return `${(bytesPerSecond / (1024 * 1024)).toFixed(1)} MB/s`;
  };

  // 获取使用率颜色
  const getUsageColor = (usage: number): string => {
    if (usage < 50) return 'text-green-600';
    if (usage < 80) return 'text-yellow-600';
    return 'text-red-600';
  };

  // 获取状态图标
  const getStatusIcon = (status: 'online' | 'offline') => {
    if (status === 'online') {
      return <CheckCircle2 className="size-5 text-green-500" />;
    }
    return <AlertCircle className="size-5 text-red-500" />;
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">系统监控</h2>
          <p className="text-muted-foreground mt-1">实时监控系统资源和应用状态</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={autoRefresh ? 'default' : 'outline'}
            size="sm"
            onClick={() => setAutoRefresh(!autoRefresh)}
          >
            <Activity className={`size-4 mr-2 ${autoRefresh ? 'animate-pulse' : ''}`} />
            {autoRefresh ? '自动刷新' : '已暂停'}
          </Button>
          <Button variant="outline" onClick={fetchSystemInfo} disabled={loading}>
            <RefreshCw className={`size-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
        </div>
      </div>

      {/* Backend Status */}
      <Card className={systemInfo.backend_status === 'online' ? 'border-green-500' : 'border-red-500'}>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {getStatusIcon(systemInfo.backend_status)}
              <div>
                <CardTitle>后端服务状态</CardTitle>
                <CardDescription>
                  {systemInfo.backend_status === 'online' ? 'Python FastAPI 后端运行正常' : '后端服务离线'}
                </CardDescription>
              </div>
            </div>
            <div className="text-right">
              <Badge variant={systemInfo.backend_status === 'online' ? 'default' : 'destructive'}>
                {systemInfo.backend_status === 'online' ? '在线' : '离线'}
              </Badge>
              <p className="text-sm text-muted-foreground mt-1">
                运行时间: {systemInfo.uptime}
              </p>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* System Resources */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* CPU Usage */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Cpu className="size-5 text-primary" />
                <CardTitle className="text-base">CPU 使用率</CardTitle>
              </div>
              <span className={`text-2xl font-bold ${getUsageColor(systemInfo.cpu_usage)}`}>
                {systemInfo.cpu_usage}%
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <Progress value={systemInfo.cpu_usage} className="h-2" />
            <p className="text-xs text-muted-foreground mt-2">
              {systemInfo.cpu_usage < 50 ? '运行流畅' : systemInfo.cpu_usage < 80 ? '负载适中' : '负载较高'}
            </p>
          </CardContent>
        </Card>

        {/* Memory Usage */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <MemoryStick className="size-5 text-primary" />
                <CardTitle className="text-base">内存使用率</CardTitle>
              </div>
              <span className={`text-2xl font-bold ${getUsageColor(systemInfo.memory_usage)}`}>
                {systemInfo.memory_usage}%
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <Progress value={systemInfo.memory_usage} className="h-2" />
            <p className="text-xs text-muted-foreground mt-2">
              {systemInfo.memory_usage < 50 ? '充足' : systemInfo.memory_usage < 80 ? '适中' : '偏高'}
            </p>
          </CardContent>
        </Card>

        {/* Disk Usage */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <HardDrive className="size-5 text-primary" />
                <CardTitle className="text-base">磁盘使用率</CardTitle>
              </div>
              <span className={`text-2xl font-bold ${getUsageColor(systemInfo.disk_usage)}`}>
                {systemInfo.disk_usage}%
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <Progress value={systemInfo.disk_usage} className="h-2" />
            <p className="text-xs text-muted-foreground mt-2">
              {systemInfo.disk_usage < 50 ? '空间充足' : systemInfo.disk_usage < 80 ? '空间适中' : '空间不足'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Network Speed */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Network className="size-5 text-primary" />
            <CardTitle>网络速度</CardTitle>
          </div>
          <CardDescription>实时下载和上传速度</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <TrendingDown className="size-4 text-green-500" />
                  <span className="text-sm font-medium">下载速度</span>
                </div>
                <Badge variant="outline">{formatSpeed(systemInfo.network_speed.download)}</Badge>
              </div>
              <Progress value={Math.min((systemInfo.network_speed.download / (10 * 1024 * 1024)) * 100, 100)} className="h-2" />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <TrendingUp className="size-4 text-blue-500" />
                  <span className="text-sm font-medium">上传速度</span>
                </div>
                <Badge variant="outline">{formatSpeed(systemInfo.network_speed.upload)}</Badge>
              </div>
              <Progress value={Math.min((systemInfo.network_speed.upload / (10 * 1024 * 1024)) * 100, 100)} className="h-2" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Download Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">活动任务</p>
                <p className="text-3xl font-bold text-blue-600">{systemInfo.active_tasks}</p>
              </div>
              <Zap className="size-12 text-blue-500 opacity-20" />
            </div>
            <Progress value={(systemInfo.active_tasks / 10) * 100} className="h-1 mt-3" />
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">队列任务</p>
                <p className="text-3xl font-bold text-yellow-600">{systemInfo.queue_size}</p>
              </div>
              <Server className="size-12 text-yellow-500 opacity-20" />
            </div>
            <Progress value={(systemInfo.queue_size / 20) * 100} className="h-1 mt-3" />
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">总下载数</p>
                <p className="text-3xl font-bold text-green-600">{systemInfo.total_downloads}</p>
              </div>
              <Database className="size-12 text-green-500 opacity-20" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Backend Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="size-5" />
            后端信息
          </CardTitle>
          <CardDescription>Python FastAPI 后端服务详情</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">服务地址</span>
              <p className="font-mono">{getApiBaseUrl()}</p>
            </div>
            <div>
              <span className="text-muted-foreground">API 版本</span>
              <p className="font-medium">v1.0.0</p>
            </div>
            <div>
              <span className="text-muted-foreground">Python 版本</span>
              <p className="font-medium">3.14.0</p>
            </div>
            <div>
              <span className="text-muted-foreground">FastAPI 版本</span>
              <p className="font-medium">0.104.0</p>
            </div>
          </div>
          
          <Separator />
          
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => window.open(`${getApiBaseUrl()}/docs`, '_blank')}>
              <Server className="size-4 mr-2" />
              API 文档
            </Button>
            <Button variant="outline" size="sm" onClick={() => window.open(`${getApiBaseUrl()}/health`, '_blank')}>
              <Activity className="size-4 mr-2" />
              健康检查
            </Button>
            <Button variant="outline" size="sm" onClick={() => toast.info('功能开发中')}>
              <FolderOpen className="size-4 mr-2" />
              打开日志
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Storage Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="size-5" />
            存储信息
          </CardTitle>
          <CardDescription>应用数据和缓存使用情况</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
              <div>
                <p className="font-medium">数据库文件</p>
                <p className="text-sm text-muted-foreground">backend/data/vidflow.db</p>
              </div>
              <Badge variant="outline">2.4 MB</Badge>
            </div>
            
            <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
              <div>
                <p className="font-medium">临时文件</p>
                <p className="text-sm text-muted-foreground">backend/data/temp/</p>
              </div>
              <Badge variant="outline">156 MB</Badge>
            </div>
            
            <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
              <div>
                <p className="font-medium">日志文件</p>
                <p className="text-sm text-muted-foreground">backend/data/logs/</p>
              </div>
              <Badge variant="outline">8.7 MB</Badge>
            </div>

            <Separator />

            <div className="flex justify-between items-center">
              <span className="text-sm font-medium">总使用空间</span>
              <span className="text-lg font-bold">167.1 MB</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Performance Tips */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="size-5 text-yellow-500" />
            性能建议
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {systemInfo.cpu_usage > 80 && (
            <div className="flex items-start gap-2 p-3 bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
              <AlertCircle className="size-4 mt-0.5 text-yellow-600 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-medium text-yellow-900 dark:text-yellow-100">CPU 使用率较高</p>
                <p className="text-yellow-700 dark:text-yellow-300">建议减少并发下载数量或关闭其他应用程序</p>
              </div>
            </div>
          )}
          
          {systemInfo.memory_usage > 80 && (
            <div className="flex items-start gap-2 p-3 bg-orange-50 dark:bg-orange-950/20 border border-orange-200 dark:border-orange-800 rounded-lg">
              <AlertCircle className="size-4 mt-0.5 text-orange-600 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-medium text-orange-900 dark:text-orange-100">内存使用率偏高</p>
                <p className="text-orange-700 dark:text-orange-300">建议清理缓存或重启应用</p>
              </div>
            </div>
          )}
          
          {systemInfo.disk_usage > 80 && (
            <div className="flex items-start gap-2 p-3 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded-lg">
              <AlertCircle className="size-4 mt-0.5 text-red-600 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-medium text-red-900 dark:text-red-100">磁盘空间不足</p>
                <p className="text-red-700 dark:text-red-300">请清理下载文件或更换下载路径</p>
              </div>
            </div>
          )}

          {systemInfo.cpu_usage < 50 && systemInfo.memory_usage < 50 && systemInfo.disk_usage < 50 && (
            <div className="flex items-start gap-2 p-3 bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800 rounded-lg">
              <CheckCircle2 className="size-4 mt-0.5 text-green-600 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-medium text-green-900 dark:text-green-100">系统运行良好</p>
                <p className="text-green-700 dark:text-green-300">所有资源使用正常，可以继续使用</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
