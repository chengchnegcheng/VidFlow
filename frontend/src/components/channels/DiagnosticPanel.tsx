import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Alert, AlertDescription } from '../ui/alert';
import {
  AlertCircle,
  AlertTriangle,
  Info,
  CheckCircle2,
  RefreshCw,
  Loader2,
} from 'lucide-react';
import { invoke } from '../TauriIntegration';
import { DiagnosticInfo, DiagnosticLevel, SystemDiagnosticResponse } from '../../types/channels';
import { toast } from 'sonner';

const LEVEL_ICONS: Record<DiagnosticLevel, React.ReactNode> = {
  error: <AlertCircle className="h-5 w-5 text-destructive" />,
  warning: <AlertTriangle className="h-5 w-5 text-yellow-500" />,
  info: <Info className="h-5 w-5 text-blue-500" />,
  success: <CheckCircle2 className="h-5 w-5 text-green-500" />,
};

const LEVEL_STYLES: Record<DiagnosticLevel, string> = {
  error: 'border-destructive/50 bg-destructive/10',
  warning: 'border-yellow-500/50 bg-yellow-500/10',
  info: 'border-blue-500/50 bg-blue-500/10',
  success: 'border-green-500/50 bg-green-500/10',
};

export const DiagnosticPanel: React.FC = () => {
  const [diagnostic, setDiagnostic] = React.useState<SystemDiagnosticResponse | null>(null);
  const [captureDiagnostic, setCaptureDiagnostic] = React.useState<DiagnosticInfo | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [rawJson, setRawJson] = React.useState('');

  const runDiagnostic = React.useCallback(async () => {
    setIsLoading(true);
    try {
      const [systemResult, captureResult] = await Promise.all([
        invoke('channels_diagnose') as Promise<SystemDiagnosticResponse>,
        invoke('channels_get_diagnostics') as Promise<DiagnosticInfo>,
      ]);
      setDiagnostic(systemResult);
      setCaptureDiagnostic(captureResult);
      setRawJson(
        JSON.stringify(
          {
            system: systemResult,
            capture: captureResult,
          },
          null,
          2,
        ),
      );
    } catch (error: any) {
      toast.error('Diagnostic failed', { description: error.message });
      setRawJson(`Error: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void runDiagnostic();
  }, [runDiagnostic]);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg">System Diagnostics</CardTitle>
            <CardDescription>
              Check environment status and surface recent Channels capture logs automatically.
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={runDiagnostic} disabled={isLoading}>
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {diagnostic && (
          <>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="space-y-1">
                <div className="text-muted-foreground">Admin</div>
                <div className={diagnostic.is_admin ? 'text-green-600' : 'text-red-600'}>
                  {diagnostic.is_admin ? 'Granted' : 'Missing'}
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-muted-foreground">WeChat Processes</div>
                <div className={diagnostic.wechat_running ? 'text-green-600' : 'text-yellow-600'}>
                  {diagnostic.wechat_running ? `Running (${diagnostic.wechat_processes.length})` : 'Not running'}
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-muted-foreground">Sniffer State</div>
                <div>
                  {diagnostic.sniffer_state === 'running'
                    ? 'Running'
                    : diagnostic.sniffer_state === 'stopped'
                      ? 'Stopped'
                      : diagnostic.sniffer_state}
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-muted-foreground">Detected Videos</div>
                <div className={diagnostic.videos_detected > 0 ? 'text-green-600' : ''}>
                  {diagnostic.videos_detected}
                </div>
              </div>
            </div>

            {diagnostic.wechat_processes.length > 0 && (
              <div className="space-y-2">
                <div className="text-sm font-medium">WeChat Process Details</div>
                <div className="space-y-1 text-xs">
                  {diagnostic.wechat_processes.map((proc) => (
                    <div key={proc.pid} className="flex items-center gap-2 text-muted-foreground">
                      <span className="font-mono">{proc.name}</span>
                      <span>PID: {proc.pid}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {diagnostic.recommendations.length > 0 && (
              <div className="space-y-2">
                <div className="text-sm font-medium">Recommendations</div>
                <div className="space-y-2">
                  {diagnostic.recommendations.map((rec, index) => (
                    <Alert key={`${index}-${rec.message}`} className={LEVEL_STYLES[rec.level]}>
                      <div className="flex items-start gap-3">
                        {LEVEL_ICONS[rec.level]}
                        <div className="flex-1 space-y-1">
                          <AlertDescription className="font-medium">{rec.message}</AlertDescription>
                          <AlertDescription className="text-sm text-muted-foreground">
                            {rec.action}
                          </AlertDescription>
                        </div>
                      </div>
                    </Alert>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {captureDiagnostic && (
          <>
            {captureDiagnostic.recent_errors.length > 0 && (
              <div className="space-y-2">
                <div className="text-sm font-medium">Recent Critical Events</div>
                <div className="space-y-2">
                  {captureDiagnostic.recent_errors.map((entry, index) => (
                    <Alert key={`${index}-${entry}`} className="border-yellow-500/50 bg-yellow-500/10">
                      <div className="flex items-start gap-3">
                        <AlertTriangle className="h-5 w-5 text-yellow-600" />
                        <AlertDescription className="text-sm">{entry}</AlertDescription>
                      </div>
                    </Alert>
                  ))}
                </div>
              </div>
            )}

            <div className="space-y-2">
              <div className="flex items-center justify-between gap-4">
                <div className="text-sm font-medium">Recent Capture Logs</div>
                <div className="text-right text-xs text-muted-foreground break-all">
                  {String(captureDiagnostic.statistics?.diagnostic_log_file || 'backend/data/logs/app.log')}
                </div>
              </div>
              <pre className="max-h-80 overflow-auto rounded-lg bg-muted p-4 text-xs whitespace-pre-wrap break-all">
                {captureDiagnostic.capture_log.length > 0
                  ? captureDiagnostic.capture_log.join('\n')
                  : 'No recent Channels log entries.'}
              </pre>
            </div>

            {captureDiagnostic.recent_response_samples && captureDiagnostic.recent_response_samples.length > 0 && (
              <div className="space-y-2">
                <div className="text-sm font-medium">Recent Capture Hints</div>
                <div className="space-y-2">
                  {captureDiagnostic.recent_response_samples.slice(-10).reverse().map((sample, index) => (
                    <div key={`${sample.classification}-${sample.path}-${index}`} className="rounded-lg border bg-muted/40 p-3 text-xs">
                      <div className="font-medium">{sample.classification}</div>
                      <div className="mt-1 break-all text-muted-foreground">
                        {sample.host}
                        {sample.path}
                      </div>
                      {sample.detail && (
                        <div className="mt-1 break-all text-muted-foreground">{sample.detail}</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {!diagnostic && !captureDiagnostic && !isLoading && (
          <div className="py-8 text-center text-muted-foreground">Click refresh to run diagnostics.</div>
        )}

        {rawJson && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="text-sm font-medium">Raw Diagnostic JSON</div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  navigator.clipboard.writeText(rawJson);
                  toast.success('Copied to clipboard');
                }}
              >
                Copy
              </Button>
            </div>
            <pre className="max-h-96 overflow-auto rounded-lg bg-muted p-4 text-xs">{rawJson}</pre>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default DiagnosticPanel;
