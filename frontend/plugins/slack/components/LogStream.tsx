"use client";

import { useEffect, useReducer, useRef, useCallback } from "react";
import { RefreshCw, Plug } from "lucide-react";
import { Spinner } from "@/components/Spinner";
import { useAuth } from "@/lib/auth-context";
import {
  fetchLogs,
  type BotResponseLogItem,
  type ConnectionLogItem,
  type LogItem,
} from "@/lib/slack-api";

const POLL_INTERVAL_MS = 30_000;
const PAGE_SIZE = 50;

interface LogStreamState {
  entries: LogItem[];
  nextCursor: string | null;
  hasMore: boolean;
  initialLoading: boolean;
  loadingOlder: boolean;
  polling: boolean;
  error: string | null;
  consecutivePollErrors: number;
}

type LogStreamAction =
  | { type: "INITIAL_START" }
  | { type: "INITIAL_SUCCESS"; items: LogItem[]; nextCursor: string | null; hasMore: boolean }
  | { type: "INITIAL_FAILURE"; error: string }
  | { type: "POLL_START" }
  | { type: "POLL_SUCCESS"; newItems: LogItem[] }
  | { type: "POLL_FAILURE"; error: string }
  | { type: "LOAD_OLDER_START" }
  | { type: "LOAD_OLDER_SUCCESS"; items: LogItem[]; nextCursor: string | null; hasMore: boolean }
  | { type: "LOAD_OLDER_FAILURE"; error: string }
  | { type: "DISMISS_ERROR" };

const initial: LogStreamState = {
  entries: [],
  nextCursor: null,
  hasMore: false,
  initialLoading: true,
  loadingOlder: false,
  polling: false,
  error: null,
  consecutivePollErrors: 0,
};

function reducer(state: LogStreamState, action: LogStreamAction): LogStreamState {
  switch (action.type) {
    case "INITIAL_START":
      return { ...state, initialLoading: true, error: null };
    case "INITIAL_SUCCESS":
      return {
        ...state,
        entries: action.items,
        nextCursor: action.nextCursor,
        hasMore: action.hasMore,
        initialLoading: false,
        consecutivePollErrors: 0,
      };
    case "INITIAL_FAILURE":
      return { ...state, initialLoading: false, error: action.error };
    case "POLL_START":
      return { ...state, polling: true };
    case "POLL_SUCCESS":
      return {
        ...state,
        polling: false,
        entries: [...[...action.newItems].reverse(), ...state.entries],
        consecutivePollErrors: 0,
        error: null,
      };
    case "POLL_FAILURE": {
      const next = state.consecutivePollErrors + 1;
      return {
        ...state,
        polling: false,
        consecutivePollErrors: next,
        error: next >= 2 ? action.error : state.error,
      };
    }
    case "LOAD_OLDER_START":
      return { ...state, loadingOlder: true };
    case "LOAD_OLDER_SUCCESS":
      return {
        ...state,
        loadingOlder: false,
        entries: [...state.entries, ...action.items],
        nextCursor: action.nextCursor,
        hasMore: action.hasMore,
      };
    case "LOAD_OLDER_FAILURE":
      return { ...state, loadingOlder: false, error: action.error };
    case "DISMISS_ERROR":
      return { ...state, error: null };
  }
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { timeZoneName: "short" });
}

function responseTypeLabel(responseType: string): { label: string; className: string } {
  switch (responseType) {
    case "rag_match":
      return { label: "matched", className: "text-success-400" };
    case "fallback":
      return { label: "no match — fallback", className: "text-zinc-500" };
    case "greeting":
      return { label: "greeting", className: "text-zinc-500" };
    case "config_incomplete":
      return { label: "config incomplete", className: "text-amber-400" };
    case "plugin_disabled":
      return { label: "plugin disabled", className: "text-amber-400" };
    default:
      return { label: responseType, className: "text-zinc-500" };
  }
}

function MessageRow({ entry }: { entry: BotResponseLogItem }) {
  const userDisplay = entry.slack_user_name ?? `@${entry.slack_user}`;
  const channelDisplay = entry.slack_channel_name
    ? `#${entry.slack_channel_name}`
    : `#${entry.slack_channel}`;
  const { label, className } = responseTypeLabel(entry.response_type);

  return (
    <article className="px-4 py-2 border-t border-zinc-800 first:border-t-0">
      <div className="text-zinc-500">
        {formatTimestamp(entry.created_at)} · {userDisplay} in {channelDisplay}
      </div>
      <div className="mt-1">
        <span className="text-zinc-400">Q:</span> {entry.question}
      </div>
      <div>
        <span className="text-zinc-400">A:</span>{" "}
        {entry.answer ?? <span className="italic text-zinc-500">&lt;no answer&gt;</span>}
      </div>
      <div className="mt-1">
        <span className={className}>{label}</span>
      </div>
    </article>
  );
}

function ConnectionRow({ entry }: { entry: ConnectionLogItem }) {
  const verb = entry.event_type === "connected" ? "Connected to" : "Disconnected from";
  const name = entry.team_name ? `"${entry.team_name}"` : "workspace";
  return (
    <div className="px-4 py-2 border-t border-zinc-800 first:border-t-0 flex items-center gap-2 text-zinc-400">
      <Plug className="w-3.5 h-3.5 flex-shrink-0" aria-hidden="true" />
      <span>
        {verb} {name}
      </span>
      <span className="ml-auto text-zinc-600 text-xs">{formatTimestamp(entry.created_at)}</span>
    </div>
  );
}

export default function LogStream() {
  const { token } = useAuth();
  const [state, dispatch] = useReducer(reducer, initial);
  const containerRef = useRef<HTMLDivElement>(null);
  const wasAtTopRef = useRef(true);
  const shouldScrollTopRef = useRef(false);
  const stateRef = useRef(state);
  useEffect(() => {
    stateRef.current = state;
  });

  const loadInitial = useCallback(async () => {
    if (!token) return;
    dispatch({ type: "INITIAL_START" });
    try {
      const data = await fetchLogs(token, { limit: PAGE_SIZE });
      dispatch({
        type: "INITIAL_SUCCESS",
        items: data.items,
        nextCursor: data.next_cursor,
        hasMore: data.has_more,
      });
    } catch (err) {
      dispatch({
        type: "INITIAL_FAILURE",
        error: err instanceof Error ? err.message : "Failed to load logs",
      });
    }
  }, [token]);

  useEffect(() => {
    loadInitial();
  }, [loadInitial]);

  const pollOnce = useCallback(async () => {
    if (!token) return;
    const { initialLoading, polling, loadingOlder, entries } = stateRef.current;
    if (initialLoading || polling || loadingOlder) return;

    const sinceId = entries
      .filter((e): e is BotResponseLogItem => e.type === "message")
      .reduce<number | undefined>(
        (max, e) => (max === undefined || e.id > max ? e.id : max),
        undefined,
      );

    if (sinceId === undefined) {
      await loadInitial();
      return;
    }
    dispatch({ type: "POLL_START" });
    const c = containerRef.current;
    wasAtTopRef.current = c ? c.scrollTop <= 50 : true;
    try {
      const data = await fetchLogs(token, { sinceId, limit: PAGE_SIZE });
      shouldScrollTopRef.current = wasAtTopRef.current;
      dispatch({ type: "POLL_SUCCESS", newItems: data.items });
    } catch (err) {
      dispatch({
        type: "POLL_FAILURE",
        error: err instanceof Error ? err.message : "Polling failed",
      });
    }
  }, [token, loadInitial]);

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | undefined;

    const start = () => {
      if (intervalId !== undefined) return;
      intervalId = setInterval(() => {
        if (document.visibilityState === "visible") pollOnce();
      }, POLL_INTERVAL_MS);
    };
    const stop = () => {
      if (intervalId !== undefined) {
        clearInterval(intervalId);
        intervalId = undefined;
      }
    };

    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        pollOnce();
        start();
      } else {
        stop();
      }
    };

    if (document.visibilityState === "visible") start();
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [pollOnce]);

  useEffect(() => {
    if (shouldScrollTopRef.current && containerRef.current) {
      containerRef.current.scrollTop = 0;
      shouldScrollTopRef.current = false;
    }
  }, [state.entries.length]);

  const loadOlder = useCallback(async () => {
    if (!token || !state.hasMore || state.nextCursor === null || state.loadingOlder) return;
    dispatch({ type: "LOAD_OLDER_START" });
    try {
      const data = await fetchLogs(token, { cursor: state.nextCursor, limit: PAGE_SIZE });
      dispatch({
        type: "LOAD_OLDER_SUCCESS",
        items: data.items,
        nextCursor: data.next_cursor,
        hasMore: data.has_more,
      });
    } catch (err) {
      dispatch({
        type: "LOAD_OLDER_FAILURE",
        error: err instanceof Error ? err.message : "Failed to load older entries",
      });
    }
  }, [token, state.hasMore, state.nextCursor, state.loadingOlder]);

  return (
    <div className="bg-zinc-950 text-zinc-100 rounded-lg overflow-hidden border border-zinc-800">
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800 bg-zinc-900">
        <span className="text-sm font-medium">Response logs</span>
        <button
          type="button"
          onClick={pollOnce}
          disabled={state.polling || state.initialLoading}
          className="inline-flex items-center gap-1 text-xs text-zinc-300 hover:text-white disabled:opacity-50"
          aria-label="Refresh logs"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 ${state.polling ? "animate-spin" : ""}`}
            aria-hidden="true"
          />
          Refresh
        </button>
      </div>

      {state.error && (
        <div className="px-4 py-2 bg-error-900/50 border-b border-error-800 text-xs text-error-200 flex items-center justify-between">
          <span>{state.error}</span>
          <button
            type="button"
            onClick={() => dispatch({ type: "DISMISS_ERROR" })}
            className="text-error-200 hover:text-white text-xs underline"
          >
            Dismiss
          </button>
        </div>
      )}

      <div
        ref={containerRef}
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        className="font-mono text-xs overflow-y-auto"
        style={{ maxHeight: "60vh" }}
      >
        {state.initialLoading ? (
          <div className="flex items-center justify-center py-12">
            <Spinner className="text-zinc-400" />
          </div>
        ) : state.entries.length === 0 ? (
          <div className="px-4 py-12 text-center text-zinc-500">
            Waiting for student questions… The bot&apos;s responses will appear here.
          </div>
        ) : (
          <>
            {state.entries.map((entry) =>
              entry.type === "message" ? (
                <MessageRow key={`msg-${entry.id}`} entry={entry} />
              ) : (
                <ConnectionRow key={`conn-${entry.id}`} entry={entry} />
              ),
            )}

            {state.hasMore && (
              <div className="px-4 py-3 border-t border-zinc-800 text-center">
                <button
                  type="button"
                  onClick={loadOlder}
                  disabled={state.loadingOlder}
                  className="text-xs text-zinc-300 hover:text-white disabled:opacity-50"
                >
                  {state.loadingOlder ? "Loading…" : "↑ Load older"}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
