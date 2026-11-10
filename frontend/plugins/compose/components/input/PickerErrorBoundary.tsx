"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

interface PickerErrorBoundaryProps {
  children: ReactNode;
  /** Called once the picker failed to load or render, so the caller can close it and say so. */
  onError: () => void;
}

interface PickerErrorBoundaryState {
  failed: boolean;
}

/**
 * Contains an attachment source's picker, so a picker that fails to load or render closes instead
 * of taking down the whole Compose page.
 */
export class PickerErrorBoundary extends Component<
  PickerErrorBoundaryProps,
  PickerErrorBoundaryState
> {
  state: PickerErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): PickerErrorBoundaryState {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("compose: the attachment picker failed", error, info.componentStack);
    this.props.onError();
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}
