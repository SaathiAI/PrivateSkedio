import { Component } from "react";
import { tokens } from "../theme.js";

export class ViewErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidUpdate(prevProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  componentDidCatch(error) {
    console.error("SkedioAI view crashed:", error);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div style={{
        padding: 24,
        margin: 24,
        border: `1px solid ${tokens.red}`,
        borderRadius: 12,
        background: tokens.redBg,
        color: tokens.red,
        fontSize: 13,
        lineHeight: 1.6,
      }}>
        <div style={{ fontWeight: 700, marginBottom: 6 }}>This view hit an error.</div>
        <div>{this.state.error?.message || "Unknown UI error"}</div>
        {this.props.onAction && (
          <button
            onClick={this.props.onAction}
            style={{
              marginTop: 14,
              padding: "8px 12px",
              borderRadius: 8,
              border: `1px solid ${tokens.border}`,
              background: tokens.bg,
              color: tokens.text,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            {this.props.actionLabel || "Back"}
          </button>
        )}
      </div>
    );
  }
}
