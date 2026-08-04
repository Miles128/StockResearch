import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 24, color: "#ff6b6b", fontFamily: "monospace" }}>
          <h2>Something went wrong</h2>
          <pre style={{ whiteSpace: "pre-wrap", fontSize: 13 }}>{this.state.error?.message}</pre>
          <button
            type="button"
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{ marginTop: 12, padding: "6px 16px" }}
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
