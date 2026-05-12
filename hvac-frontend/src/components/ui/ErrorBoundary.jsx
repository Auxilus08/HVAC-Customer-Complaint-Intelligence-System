import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  // eslint-disable-next-line no-console
  componentDidCatch(error, info) { console.error("Component error:", error, info); }

  reset = () => this.setState({ hasError: false, error: null });

  render() {
    if (this.state.hasError) {
      return (
        <div className="card flex flex-col items-center justify-center p-8 text-center">
          <div className="text-critical text-4xl mb-3">⚠</div>
          <p className="text-ink-700 font-medium mb-1">
            Component failed to render
          </p>
          <p className="text-ink-500 text-sm mb-4 max-w-md break-words">
            {this.state.error?.message || "Unknown error"}
          </p>
          <button onClick={this.reset} className="btn-ghost text-sm">
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
