import { Component, ReactNode } from "react";
import { emitPluginEvent } from "@/lib/plugins";
import { Button } from "@/components/ui/Button";

interface Props {
  children: ReactNode;
  pluginName: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class PluginErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error(`Plugin "${this.props.pluginName}" error:`, error, errorInfo);

    emitPluginEvent({
      type: "plugin:error",
      pluginName: this.props.pluginName,
      payload: {
        error: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
      },
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center h-full p-8">
          <div className="text-center max-w-md">
            <div className="text-error-500 mb-4">
              <svg
                className="w-16 h-16 mx-auto"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-foreground mb-2">
              Plugin Error
            </h3>
            <p className="text-muted-foreground mb-4">
              The plugin <strong>{this.props.pluginName}</strong> encountered an
              error and could not be loaded.
            </p>
            {this.state.error && (
              <p className="text-sm text-muted mb-4 font-mono">
                {this.state.error.message}
              </p>
            )}
            <Button variant="primary" onClick={() => window.location.reload()}>
              Reload Page
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
