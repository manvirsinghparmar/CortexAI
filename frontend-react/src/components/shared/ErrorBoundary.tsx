import { Component, type CSSProperties, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryState {
  error: Error | null;
}

// Without a boundary, any render-time throw unmounts the entire React tree
// and leaves a blank page that users experience as the app "refreshing" and
// losing their chat.
export class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Unhandled render error", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div role="alert" style={fallbackStyles.wrap}>
        <h1 style={fallbackStyles.title}>Something went wrong</h1>
        <p style={fallbackStyles.message}>
          The app hit an unexpected error. Your chats are saved and will be
          restored after a reload.
        </p>
        <button
          type="button"
          style={fallbackStyles.button}
          onClick={() => window.location.reload()}
        >
          Reload
        </button>
      </div>
    );
  }
}

const fallbackStyles = {
  wrap: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "12px",
    minHeight: "100vh",
    padding: "24px",
    textAlign: "center",
    fontFamily: "Manrope, system-ui, sans-serif",
  },
  title: {
    fontSize: "1.4rem",
    fontWeight: 700,
  },
  message: {
    maxWidth: "42ch",
    color: "#5c6270",
  },
  button: {
    padding: "10px 28px",
    borderRadius: "999px",
    border: "1px solid #d5d9e2",
    background: "#1f2430",
    color: "#ffffff",
    fontSize: "0.95rem",
    cursor: "pointer",
  },
} satisfies Record<string, CSSProperties>;
