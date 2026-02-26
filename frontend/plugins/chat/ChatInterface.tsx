// "use client";

// import { useEffect, useState } from "react";
// import { ChatHeader } from "./components/ChatHeader";
// import { ChatMessages } from "./components/messages/ChatMessages";
// import { ChatInput } from "./components/input/ChatInput";
// import { ChatMessage, TextAttachment } from "./types";
// import { Preview } from "./components/attachment/Preview";
// import { loadPrompt } from "@/lib/prompt";

// type ConversationStep =
//   | "idle"
//   | "prompt_generated"
//   | "audience_question"
//   | "learning_outcomes_question"
//   | "outline_review"
//   | "course_generated"
//   | "publish_course";

// export default function ChatInterface() {
//   const [step, setStep] = useState<ConversationStep>("idle");
//   const [previewOpen, setPreviewOpen] = useState(false);
//   const [inputAttachment, setInputAttachment] = useState<TextAttachment | null>(
//     null,
//   );
//   const [previewAttachment, setPreviewAttachment] =
//     useState<TextAttachment | null>(null);
//   const [messages, setMessages] = useState<ChatMessage[]>([
//     {
//       id: "welcome",
//       role: "assistant",
//       content:
//         "Hi! I'm your AI course creation assistant. What would you like to create today?",
//     },
//   ]);

//   const [COURSE_PROMPT, setCoursePrompt] = useState("");
//   const [COURSE_OUTLINE, setCourseOutline] = useState("");
//   const [FINAL_COURSE, setFinalCourse] = useState("");

//   useEffect(() => {
//     async function loadAll() {
//       const [prompt, outline, course] = await Promise.all([
//         loadPrompt("/content/course_prompt.txt"),
//         loadPrompt("/content/outline.txt"),
//         loadPrompt("/content/final_course.txt"),
//       ]);

//       setCoursePrompt(prompt);
//       setCourseOutline(outline);
//       setFinalCourse(course);
//     }
//     loadAll();
//   }, []);

//   const streamMessage = async (id: string, fullText: string) => {
//     for (let i = 0; i <= fullText.length; i++) {
//       setMessages((prev) =>
//         prev.map((msg) =>
//           msg.id === id
//             ? {
//                 ...msg,
//                 streamedContent: fullText.slice(0, i),
//                 isTyping: i < fullText.length,
//               }
//             : msg,
//         ),
//       );
//       await new Promise((r) => setTimeout(r, 20));
//     }
//   };

//   // const handleSend = async ({
//   //   message,
//   //   attachment,
//   // }: {
//   //   message: string;
//   //   attachment: TextAttachment | null;
//   // }) => {
//   //   const userMessage: ChatMessage = {
//   //     id: crypto.randomUUID(),
//   //     role: "user",
//   //     content: message || "Uploaded a document",
//   //     attachment,
//   //   };
//   //   setMessages((prev) => [...prev, userMessage]);

//   //   /* ===========================
//   //    FLOW CONTROLLER
//   // ============================ */

//   //   // STEP 1: User uploads document + asks to create course
//   //   if (step === "idle" && attachment) {
//   //     setStep("prompt_generated");

//   //     await addAssistantMessage(
//   //       "I'll help you create a course based on this Data Science and AI handbook. Let me start by extracting the key information and generating a course structure.",
//   //       {
//   //         pillAttachment: {
//   //           name: "Course Generation Prompt",
//   //           size: COURSE_PROMPT.length,
//   //           text: COURSE_PROMPT,
//   //         },
//   //       },
//   //     );

//   //     await addAssistantMessage(
//   //       "Great! I have the course generation prompt. Now let me ask you some important questions to tailor this course effectively:\n\n\nStep 1: Understanding Your Audience & Goals\n\nWhat is the background of your target learners?\n\nFor example:\n\n",
//   //       {
//   //         options: [
//   //           "They are complete beginners to data science",
//   //           "They have some programming experience",
//   //           "They are IT professionals looking to transition into data science",
//   //           "They are students, working professionals, or both",
//   //         ],
//   //       },
//   //     );

//   //     setStep("audience_question");
//   //     return;
//   //   }

//   //   // STEP 2: Audience selected (ignore actual text)
//   //   if (step === "audience_question") {
//   //     setStep("learning_outcomes_question");

//   //     await addAssistantMessage(
//   //       "Thank you! Now for the second question, what should learners be able to know and do after completing this course?",
//   //       {
//   //         options: [
//   //           "Understand the basic concepts and terminology of data science and AI",
//   //           "Set up a simple data science environment",
//   //           "Work with data teams and understand different roles",
//   //           "Make informed decisions about data infrastructure",
//   //           "Understand when and how to use different AI/ML techniques",
//   //         ],
//   //       },
//   //     );

//   //     return;
//   //   }

//   //   // STEP 3: Learning outcomes answered
//   //   if (step === "learning_outcomes_question") {
//   //     setStep("outline_review");

//   //     await addAssistantMessage(
//   //       "Perfect! Here's an outline for a 1-2 hour introductory course. Does this work for you? Should I proceed with developing the full course content based on this structure?",
//   //       {
//   //         pillAttachment: {
//   //           name: "Course Outline",
//   //           size: COURSE_OUTLINE.length,
//   //           text: COURSE_OUTLINE,
//   //         },
//   //         options: ["Approve outline", "Improve outline"],
//   //       },
//   //     );

//   //     return;
//   //   }

//   //   // STEP 4: Outline approved
//   //   if (step === "outline_review" && message.includes("Approve")) {
//   //     setStep("course_generated");

//   //     await addAssistantMessage(
//   //       "Great! Here is the complete course based on the approved outline.",
//   //       {
//   //         pillAttachment: {
//   //           name: "Generated Course",
//   //           size: FINAL_COURSE.length,
//   //           text: FINAL_COURSE,
//   //         },
//   //         options: ["Publish on Open edX"],
//   //       },
//   //     );

//   //     return;
//   //   }

//   //   // STEP 5: Publish course
//   //   if (step === "course_generated") {
//   //     setStep("publish_course");

//   //     await addAssistantMessage(
//   //       "Finally! I'll go ahead and publish this course to Open edX. You can now access your course at: https://sandbox.openedx.edly.io/courses/course-v1:DataScienceOrg+DSAI101+2026",
//   //     );

//   //     return;
//   //   }
//   // };

//   const handleSend = async ({
//     message,
//     attachment,
//   }: {
//     message: string;
//     attachment: TextAttachment | null;
//   }) => {
//     const userMessage: ChatMessage = {
//       id: crypto.randomUUID(),
//       role: "user",
//       content: message || "Uploaded a document",
//       attachment,
//     };
//     setMessages((prev) => [...prev, userMessage]);

//     /* ===========================
//      FLOW CONTROLLER
//   ============================ */

//     // STEP 1: User uploads document + asks to create course
//     if (step === "idle" && attachment) {
//       setStep("prompt_generated");

//       await addAssistantMessage(
//         "I'll help you create a course based on this Data Science and AI handbook. Let me start by extracting the key information and generating a course structure.",
//         {
//           pillAttachment: {
//             name: "Course Generation Prompt",
//             size: COURSE_PROMPT.length,
//             text: COURSE_PROMPT,
//           },
//         },
//       );

//       await addAssistantMessage(
//         "Great! I have the course generation prompt. Now let me ask you some important questions to tailor this course effectively:\n\n\nStep 1: Understanding Your Audience & Goals\n\nWhat is the background of your target learners?\n\nFor example:\n\n",
//         {
//           options: [
//             "They are complete beginners to data science",
//             "They have some programming experience",
//             "They are IT professionals looking to transition into data science",
//             "They are students, working professionals, or both",
//           ],
//         },
//       );

//       setStep("audience_question");
//       return;
//     }

//     // STEP 2: Audience selected (ignore actual text)
//     if (step === "audience_question") {
//       setStep("learning_outcomes_question");

//       await addAssistantMessage(
//         "Thank you! Now for the second question, what should learners be able to know and do after completing this course?",
//         {
//           options: [
//             "Understand the basic concepts and terminology of data science and AI",
//             "Set up a simple data science environment",
//             "Work with data teams and understand different roles",
//             "Make informed decisions about data infrastructure",
//             "Understand when and how to use different AI/ML techniques",
//           ],
//         },
//       );

//       return;
//     }

//     // STEP 3: Learning outcomes answered
//     if (step === "learning_outcomes_question") {
//       setStep("outline_review");

//       await addAssistantMessage(
//         "Perfect! Here's an outline for a 1-2 hour introductory course. Does this work for you? Should I proceed with developing the full course content based on this structure?",
//         {
//           pillAttachment: {
//             name: "Course Outline",
//             size: COURSE_OUTLINE.length,
//             text: COURSE_OUTLINE,
//           },
//           options: ["Approve outline", "Improve outline"],
//         },
//       );

//       return;
//     }

//     // STEP 4: Outline approved
//     if (step === "outline_review" && message.includes("Approve")) {
//       setStep("course_generated");

//       await addAssistantMessage(
//         "Great! Here is the complete course based on the approved outline.",
//         {
//           pillAttachment: {
//             name: "Generated Course",
//             size: FINAL_COURSE.length,
//             text: FINAL_COURSE,
//           },
//           options: ["Publish on Open edX"],
//         },
//       );

//       return;
//     }

//     // STEP 5: Publish course
//     if (step === "course_generated") {
//       setStep("publish_course");

//       await addAssistantMessage(
//         "Finally! I'll go ahead and publish this course to Open edX. You can now access your course at: https://sandbox.openedx.edly.io/courses/course-v1:DataScienceOrg+DSAI101+2026",
//       );

//       return;
//     }
//   };

//   const addAssistantMessage = async (
//     text: string,
//     extras?: Partial<ChatMessage>,
//   ) => {
//     const msg: ChatMessage = {
//       id: crypto.randomUUID(),
//       role: "assistant",
//       content: "",
//       streamedContent: "",
//       isTyping: true,
//       ...extras,
//     };

//     setMessages((prev) => [...prev, msg]);
//     await new Promise((r) => setTimeout(r, 20));
//     await streamMessage(msg.id, text);
//   };

//   return (
//     <div className="flex flex-col h-full bg-background transition-colors">
//       <ChatHeader />
//       <ChatMessages
//         messages={messages}
//         setPreviewOpen={setPreviewOpen}
//         setPreviewAttachment={setPreviewAttachment}
//         onSend={handleSend}
//       />
//       <ChatInput
//         attachment={inputAttachment}
//         setAttachment={setInputAttachment}
//         setPreviewOpen={setPreviewOpen}
//         setPreviewAttachment={setPreviewAttachment}
//         onSend={handleSend}
//       />

//       {previewOpen && previewAttachment && (
//         <Preview
//           attachment={previewAttachment}
//           onClose={() => {
//             setPreviewOpen(false);
//             setPreviewAttachment(null);
//           }}
//         />
//       )}
//     </div>
//   );
// }

"use client";

import { useState } from "react";
import { ChatHeader } from "./components/ChatHeader";
import { ChatMessages } from "./components/messages/ChatMessages";
import { ChatInput } from "./components/input/ChatInput";
import { ChatMessage, TextAttachment } from "./types";
import { Preview } from "./components/attachment/Preview";
import { useAuth } from "@/lib/auth-context";

export default function ChatInterface() {
  const { token } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Hi! Upload a document or tell me what you’d like to create.",
    },
  ]);

  const [conversation, setConversation] = useState<
    Pick<ChatMessage, "role" | "content">[]
  >([]);

  const [previewOpen, setPreviewOpen] = useState(false);
  const [inputAttachment, setInputAttachment] = useState<TextAttachment | null>(
    null,
  );
  const [previewAttachment, setPreviewAttachment] =
    useState<TextAttachment | null>(null);

  const handleSend = async ({
    message,
    attachment,
  }: {
    message: string;
    attachment: TextAttachment | null;
  }) => {
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: message || "Uploaded a document",
      attachment,
    };

    setMessages((prev) => [...prev, userMessage]);

    const newUserMessages: Pick<ChatMessage, "role" | "content">[] = [];

    if (attachment?.text) {
      newUserMessages.push({
        role: "user",
        content: attachment.text,
      });
    }

    if (message.trim()) {
      newUserMessages.push({
        role: "user",
        content: message,
      });
    }

    const outgoingMessages = [...conversation, ...newUserMessages];

    const assistantId = crypto.randomUUID();

    setMessages((prev) => [
      ...prev,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        streamedContent: "",
        isTyping: true,
      },
    ]);

    const res = await fetch("/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        provider: "anthropic",
        model: "claude-sonnet-4-20250514",
        messages: outgoingMessages,
        stream: true,
        tools: "*",
        tool_choice: "auto",
        include_system_tools_message: true,
      }),
    });

    if (!res.body) {
      throw new Error("No response body for streaming");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");

    let assistantText = "";
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE messages are separated by newlines
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;

        const payload = trimmed.replace(/^data:\s*/, "");
        if (!payload) continue;

        try {
          const parsed = JSON.parse(payload);

          if (parsed.token) {
            assistantText += parsed.token;

            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId
                  ? {
                      ...msg,
                      streamedContent: assistantText,
                    }
                  : msg,
              ),
            );
          }

          if (parsed.done) {
            break;
          }
        } catch (err) {
          console.error("Failed to parse SSE payload:", payload, err);
        }
      }
    }

    /* ---------- Finalize assistant message ---------- */
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === assistantId
          ? {
              ...msg,
              content: assistantText,
              streamedContent: undefined,
              isTyping: false,
            }
          : msg,
      ),
    );

    /* ---------- Persist conversation ---------- */
    setConversation((prev) => [
      ...prev,
      ...newUserMessages,
      { role: "assistant", content: assistantText },
    ]);
  };

  return (
    <div className="flex flex-col h-full bg-background transition-colors">
      <ChatHeader />

      <ChatMessages
        messages={messages}
        setPreviewOpen={setPreviewOpen}
        setPreviewAttachment={setPreviewAttachment}
        onSend={handleSend}
      />

      <ChatInput
        attachment={inputAttachment}
        setAttachment={setInputAttachment}
        setPreviewOpen={setPreviewOpen}
        setPreviewAttachment={setPreviewAttachment}
        onSend={handleSend}
      />

      {previewOpen && previewAttachment && (
        <Preview
          attachment={previewAttachment}
          onClose={() => {
            setPreviewOpen(false);
            setPreviewAttachment(null);
          }}
        />
      )}
    </div>
  );
}
