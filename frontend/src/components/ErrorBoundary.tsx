import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw, Home, Terminal } from "lucide-react";

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("UI Render Error:", error, errorInfo);
    this.setState({ error, errorInfo });
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  handleReturnOverview = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      const { error, errorInfo } = this.state;
      const errorMessage = error?.message || "Unknown error";
      const stack = errorInfo?.componentStack || "";

      return (
        <div className="flex flex-col h-full items-center justify-center bg-[#070B12] text-[#E8EDF3] p-8">
          <div className="max-w-2xl w-full text-center space-y-6">
            <AlertTriangle className="w-16 h-16 text-[#D99A24] mx-auto flex-shrink-0" />
            <div className="space-y-2">
              <h2 className="font-sans font-semibold text-[22px] text-[#E8EDF3]">UI RENDER ERROR</h2>
              <p className="font-sans text-[13px] text-[#738397]">
                The visualization encountered an unexpected frontend error.
              </p>
              <p className="font-sans text-[12px] text-[#AAB7C5]">
                The tracking engine remains protected and continues running.
              </p>
            </div>

            <details className="text-left bg-[#0B111B] border border-[#26364A] rounded p-4 space-y-3">
              <summary className="font-sans text-[11px] text-[#738397] cursor-pointer flex items-center gap-2">
                <Terminal className="w-4 h-4" />
                SHOW DIAGNOSTICS
              </summary>
              <div className="font-mono text-[10px] text-[#D9534F] whitespace-pre-wrap overflow-auto max-h-64">
                {errorMessage}
              </div>
              <div className="font-mono text-[9px] text-[#556677] whitespace-pre-wrap overflow-auto max-h-64">
                {stack}
              </div>
            </details>

            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                onClick={this.handleRetry}
                className="flex items-center gap-2 px-4 py-2 rounded border border-[#1F78B4] bg-[#155A8A] text-[#E8EDF3] font-sans text-[12px] font-medium hover:bg-[#1F78B4] transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                RETRY VIEW
              </button>
              <button
                onClick={this.handleReturnOverview}
                className="flex items-center gap-2 px-4 py-2 rounded border border-[#26364A] bg-[#111A28] text-[#AAB7C5] font-sans text-[12px] font-medium hover:bg-[#162133] transition-colors"
              >
                <Home className="w-4 h-4" />
                RETURN TO OVERVIEW
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}