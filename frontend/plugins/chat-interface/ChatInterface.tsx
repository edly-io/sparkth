"use client";

import { useState } from "react";
import { Send, Paperclip } from "lucide-react";

export default function ChatInterface() {
  const [message, setMessage] = useState("");

  return (
    <div className="flex flex-col h-full">
      <div className="border-b px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
            <span className="text-white text-sm font-semibold">AI</span>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-700">
              AI Course Creator
            </h2>
            <p className="text-sm text-gray-600">
              Transform your resources into courses with AI
            </p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          <div className="flex gap-4">
            <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0">
              <span className="text-sm">🤖</span>
            </div>
            <div className="flex-1">
              <div className="bg-white rounded-lg p-4 shadow-sm border">
                <p className="text-gray-800">
                  Hi! I am your AI course creation assistant. I can help you
                  transform your resources into engaging courses. What would you
                  like to create today?
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm text-gray-600">
                    Create a course from my course materials folder
                  </button>
                  <button className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm text-gray-600">
                    Generate a quiz from my document
                  </button>
                  <button className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm text-gray-600">
                    Build a module about AI fundamentals
                  </button>
                  <button className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm text-gray-600">
                    Convert my video into a structured lesson
                  </button>
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-2 text-gray-600">
                <p className="text-xs text-gray-500 mt-2 text-gray-600">
                  {new Date().toLocaleTimeString("en-US", {
                    hour: "numeric",
                    minute: "2-digit",
                    second: "2-digit",
                    hour12: true,
                  })}
                </p>
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="border-t bg-white p-4">
        <div className="max-w-3xl mx-auto">
          <div className="flex gap-2 items-end">
            <button className="p-2 hover:bg-gray-100 rounded-lg">
              <Paperclip className="w-5 h-5 text-gray-600" />
            </button>
            <div className="flex-1 relative">
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Describe the course you want to create..."
                className="w-full px-4 py-3 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-600"
                rows={1}
              />
            </div>
            <button className="p-3 bg-gray-800 hover:bg-gray-700 text-white rounded-lg">
              <Send className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
