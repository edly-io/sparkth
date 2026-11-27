import { AlertCircle, Bot } from "lucide-react";
import { useTranslations } from "next-intl";
import { useId } from "react";
import { Card } from "@/lib/components/ui/Card";
import { ChatMessage, PlanSnapshot, StreamStatusPhase } from "@/plugins/compose/src/types";
import { OptionsPrompt } from "@/plugins/compose/src/components/ui/messages/OptionsPrompt";
import {
  answeredOptions,
  splitOptionsBlock,
} from "@/plugins/compose/src/components/ui/messages/optionsBlock";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { truncate, DOCUMENT_DISPLAY_NAME_MAX_CHARS } from "@/plugins/compose/src/displayName";

function ThinkingDots() {
  return (
    <div data-testid="thinking-dots" className="flex items-center gap-1 py-1">
      <span className="w-2 h-2 rounded-full bg-neutral-400 dark:bg-neutral-500 animate-thinking-dot [animation-delay:0ms]" />
      <span className="w-2 h-2 rounded-full bg-neutral-400 dark:bg-neutral-500 animate-thinking-dot [animation-delay:150ms]" />
      <span className="w-2 h-2 rounded-full bg-neutral-400 dark:bg-neutral-500 animate-thinking-dot [animation-delay:300ms]" />
    </div>
  );
}

type StepState = "done" | "running" | "toDo";

/** Where the plan's step `number` stands; a step the plan waits at once the reply has ended is to do. */
function getStepState(number: number, plan: PlanSnapshot, isTyping?: boolean): StepState {
  if (number < plan.current_step || (number === plan.current_step && plan.has_current_step_run)) {
    return "done";
  }
  return number === plan.current_step && isTyping ? "running" : "toDo";
}

/** The plan a reply showed, one muted row per task, marked done, running or to do. */
function PlanList({ plan, isTyping }: { plan: PlanSnapshot; isTyping?: boolean }) {
  const t = useTranslations("compose");
  const titleId = useId();
  // Keys must stay literal t("...") calls — i18n-check only traces literal calls, not computed keys.
  const stateTexts: Record<StepState, string> = {
    done: t("planStepDone"),
    running: t("planStepRunning"),
    toDo: t("planStepToDo"),
  };
  return (
    <div className="px-1 space-y-0.5">
      <p id={titleId} className="text-xs text-neutral-400 dark:text-neutral-500">
        {t("planTitle")}
      </p>
      <ul aria-labelledby={titleId} className="space-y-0.5">
        {plan.tasks.map((task, index) => {
          const state = getStepState(index + 1, plan, isTyping);
          return (
            // Relative, so the hidden state text stays inside its row instead of stretching the page.
            <li
              key={`${index}-${task}`}
              className="relative text-xs text-neutral-400 dark:text-neutral-500 flex items-baseline gap-1.5"
            >
              <span className="sr-only">{stateTexts[state]}</span>
              {state === "running" ? (
                <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 dark:bg-neutral-500 flex-shrink-0 mt-0.5 animate-pulse" />
              ) : state === "done" ? (
                <span className="w-1.5 h-1.5 rounded-full bg-neutral-300 dark:bg-neutral-600 flex-shrink-0 mt-0.5" />
              ) : (
                <span className="w-1.5 h-1.5 rounded-full border border-neutral-300 dark:border-neutral-600 flex-shrink-0 mt-0.5" />
              )}
              <span className={state === "toDo" ? "opacity-60" : ""}>{task}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

interface AssistantMessageProps {
  message: ChatMessage;
  onOptionCheck: (option: string, previous?: string) => void;
  isLatest: boolean;
  reply?: string;
}

function formatToolName(name: string): string {
  return name.replace(/_/g, " ");
}

export function AssistantMessage({
  message,
  onOptionCheck,
  isLatest,
  reply,
}: AssistantMessageProps) {
  const t = useTranslations("compose");

  // Keys must stay literal t("...") calls — i18n-check only traces literal calls, not computed keys.
  const statusTexts: Record<StreamStatusPhase, string> = {
    generating: t("statusGenerating"),
  };
  const displayText = message.streamedContent ?? message.content;
  const { body, options, closed, single } = splitOptionsBlock(displayText);
  const toolCalls = message.toolCalls ?? [];
  // The dots stay up for every waiting state, tools running or not, so nothing flickers as a
  // turn moves between calls; the count line above the card says what has run.
  const isThinking = message.isTyping && !displayText;
  // The sentence belongs to the start of a turn: once any tool call exists, a plan is shown or a
  // running step is named above the card, that carries the state, so the card falls back to the dots.
  const statusLine =
    toolCalls.length > 0 || message.plan || message.stepLabel
      ? null
      : message.statusPhase
        ? statusTexts[message.statusPhase]
        : t("working");

  return (
    <div className="flex gap-4">
      <div className="w-8 h-8 rounded-full bg-neutral-200 dark:bg-neutral-700 flex items-center justify-center flex-shrink-0">
        <Bot className="w-4 h-4" />
      </div>

      <div className="max-w-[75%] w-fit space-y-2">
        {message.plan ? (
          <PlanList plan={message.plan} isTyping={message.isTyping} />
        ) : (
          message.isTyping &&
          message.stepLabel && (
            <div role="status" className="px-1 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 dark:bg-neutral-500 flex-shrink-0 animate-pulse" />
              <p className="text-xs text-neutral-400 dark:text-neutral-500">{message.stepLabel}</p>
            </div>
          )
        )}

        {/* RAG context indicator — outside bubble, persistent */}
        {message.ragSections && message.ragSections.length > 0 && (
          <div className="px-1 space-y-0.5">
            <p className="text-xs text-neutral-400 dark:text-neutral-500">Taking into context:</p>
            <ul className="space-y-0.5">
              {message.ragSections.slice(0, 5).map((section) => (
                <li
                  key={`${section.type}-${section.name}`}
                  className="text-xs text-neutral-400 dark:text-neutral-500 flex items-baseline gap-1.5"
                >
                  {section.state === "scanning" ? (
                    <span className="w-1.5 h-1.5 rounded-full bg-neutral-300 dark:bg-neutral-600 flex-shrink-0 mt-0.5 animate-pulse" />
                  ) : (
                    <span className="w-1 h-1 rounded-full bg-neutral-300 dark:bg-neutral-600 flex-shrink-0 mt-1" />
                  )}
                  <span className="capitalize">{section.type}</span>
                  <span className="text-neutral-300 dark:text-neutral-600">—</span>
                  <span className={section.state === "scanning" ? "opacity-50" : ""}>
                    {truncate(section.name, DOCUMENT_DISPLAY_NAME_MAX_CHARS)}
                    {section.source && (
                      <>
                        {" "}
                        from{" "}
                        <span className="opacity-70">
                          {truncate(section.source, DOCUMENT_DISPLAY_NAME_MAX_CHARS)}
                        </span>
                      </>
                    )}
                  </span>
                </li>
              ))}
              {message.ragSections.length > 5 && (
                <li className="relative group ml-2.5 w-fit">
                  <span className="text-xs text-neutral-300 dark:text-neutral-600 cursor-default underline decoration-dotted">
                    +{message.ragSections.length - 5} more
                  </span>
                  {/* Hover tooltip showing remaining sections */}
                  <div className="absolute bottom-full left-0 mb-1.5 hidden group-hover:block z-20 bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 rounded-md shadow-lg p-2 min-w-max max-w-xs">
                    <ul className="space-y-1">
                      {message.ragSections.slice(5).map((section) => (
                        <li
                          key={`${section.type}-${section.name}`}
                          className="text-xs text-neutral-500 dark:text-neutral-400 flex items-baseline gap-1.5"
                        >
                          <span className="w-1 h-1 rounded-full bg-neutral-300 dark:bg-neutral-600 flex-shrink-0 mt-1" />
                          <span className="capitalize">{section.type}</span>
                          <span className="text-neutral-300 dark:text-neutral-600">—</span>
                          <span>
                            {truncate(section.name, DOCUMENT_DISPLAY_NAME_MAX_CHARS)}
                            {section.source && (
                              <>
                                {" "}
                                from{" "}
                                <span className="opacity-70">
                                  {truncate(section.source, DOCUMENT_DISPLAY_NAME_MAX_CHARS)}
                                </span>
                              </>
                            )}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </li>
              )}
            </ul>
          </div>
        )}

        {/* Tool call progress — outside bubble, above response; same shape live and after */}
        {toolCalls.length > 0 && (
          <div className="px-1">
            <div className="relative group w-fit flex items-center gap-1.5">
              {/* Pulses for as long as the turn runs, so the count line is not static */}
              {message.isTyping && (
                <span
                  data-testid="tool-activity-indicator"
                  className="w-1.5 h-1.5 rounded-full bg-neutral-300 dark:bg-neutral-600 flex-shrink-0 animate-pulse"
                />
              )}
              <p className="text-xs text-neutral-400 dark:text-neutral-500 cursor-default underline decoration-dotted decoration-neutral-300 dark:decoration-neutral-600">
                {t("toolCallCount", { count: toolCalls.length })}
              </p>
              <div className="absolute bottom-full left-0 mb-1.5 hidden group-hover:block z-20 bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 rounded-md shadow-lg p-2 min-w-max max-w-xs">
                <ul className="space-y-1">
                  {toolCalls.map((tool, i) => (
                    <li
                      key={`${tool.name}-${i}`}
                      className="text-xs text-neutral-500 dark:text-neutral-400 flex items-center gap-1.5"
                    >
                      {tool.status === "running" ? (
                        <span className="w-1.5 h-1.5 rounded-full bg-neutral-300 dark:bg-neutral-600 flex-shrink-0 animate-pulse" />
                      ) : (
                        <span className="w-1 h-1 rounded-full bg-neutral-300 dark:bg-neutral-600 flex-shrink-0" />
                      )}
                      <span>{formatToolName(tool.name)}</span>
                      {tool.status === "running" && (
                        <span className="text-neutral-400 dark:text-neutral-500">
                          — {t("toolExecuting")}
                        </span>
                      )}
                      {tool.status === "failed" && (
                        <span className="text-red-500 dark:text-red-400">— {t("toolFailed")}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {message.isError ? (
          <Card variant="outlined" className="p-4 border-error bg-error-50">
            <div className="flex items-start gap-2 text-error-500">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <p className="text-sm">{displayText || "Something went wrong. Please try again."}</p>
            </div>
          </Card>
        ) : (
          <Card variant="outlined" className="p-4">
            {isThinking ? (
              statusLine ? (
                <div className="flex items-center gap-2 py-1">
                  <span className="w-2 h-2 rounded-full bg-neutral-400 dark:bg-neutral-500 animate-pulse" />
                  <p className="text-sm text-muted-foreground">{statusLine}</p>
                </div>
              ) : (
                <ThinkingDots />
              )
            ) : message.isPending ? (
              <div className="flex items-start gap-2">
                <span
                  data-testid="pending-indicator"
                  className="w-2 h-2 rounded-full bg-neutral-400 dark:bg-neutral-500 animate-pulse flex-shrink-0 mt-1.5"
                />
                <div className="prose prose-neutral dark:prose-invert max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
                </div>
              </div>
            ) : (
              <div className="prose prose-neutral dark:prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
              </div>
            )}

            {message.stopped && (
              <p className="mt-2 text-xs text-neutral-400 dark:text-neutral-500">{t("stopped")}</p>
            )}

            {options && (
              <OptionsPrompt
                options={options}
                single={single}
                interactive={
                  isLatest &&
                  !message.isTyping &&
                  !message.isPending &&
                  (closed || !message.stopped)
                }
                selected={reply ? answeredOptions(options, reply) : []}
                answered={!!reply}
                onOptionCheck={onOptionCheck}
              />
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
