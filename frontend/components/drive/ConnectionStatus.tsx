"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  getAuthorizationUrl,
  disconnectGoogle,
  ConnectionStatus as ConnectionStatusType,
} from "@/lib/drive";

interface ConnectionStatusProps {
  status: ConnectionStatusType | null;
  onStatusChange: () => void;
}

export default function ConnectionStatus({ status, onStatusChange }: ConnectionStatusProps) {
  const { token } = useAuth();
  const [loading, setLoading] = useState(false);

  const handleConnect = async () => {
    if (!token) return;

    setLoading(true);
    try {
      const url = await getAuthorizationUrl(token);
      window.location.href = url;
    } catch (error) {
      alert(`Failed to connect: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    if (!token) return;

    if (!confirm("Are you sure you want to disconnect Google Drive?")) {
      return;
    }

    setLoading(true);
    try {
      await disconnectGoogle(token);
      onStatusChange();
    } catch (error) {
      alert(`Failed to disconnect: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className="flex-shrink-0">
            <svg
              className="h-10 w-10 text-blue-500"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M4.433 22.576l4.068-7.045H.065l4.368 7.045zm15.134 0l4.368-7.045h-8.436l4.068 7.045zM12 1.424L4.433 14.47h15.134L12 1.424z" />
            </svg>
          </div>
          <div>
            <h3 className="text-lg font-medium text-gray-900">Google Drive</h3>
            {status?.connected ? (
              <p className="text-sm text-gray-500">
                Connected as {status.email}
              </p>
            ) : (
              <p className="text-sm text-gray-500">
                Not connected
              </p>
            )}
          </div>
        </div>

        <div>
          {status?.connected ? (
            <button
              onClick={handleDisconnect}
              disabled={loading}
              className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
            >
              {loading ? "Disconnecting..." : "Disconnect"}
            </button>
          ) : (
            <button
              onClick={handleConnect}
              disabled={loading}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Connecting..." : "Connect Google Drive"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
