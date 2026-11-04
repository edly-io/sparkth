# UX & UI behaviour

Real review comments from Sparkth pull requests: user-facing behaviour and wording.

## Example 1

**Issue:** Policy names specific OAuth scopes; describe data access more generally instead of implementation details.

**Review:**

> some specific OAuth scopes are also mentioned. do we need to include these implementation details in the privacy
> policy, or can we describe the data/access more generally?

## Example 2

**Issue:** Deleting an option line by hand leaves its checkbox checked; mention in PR description that checkboxes only
add text.

`frontend/plugins/chat/components/messages/OptionsPrompt.tsx`

```diff
+ * message box for anything else. Otherwise the boxes are disabled with `selected` checked, and an
+ * `answered` question that matched no option says so.
+ */
+export function OptionsPrompt({
+  options,
+  interactive,
+  selected,
+  answered,
+  onOptionCheck,
+}: OptionsPromptProps) {
+  const t = useTranslations("chat");
+  const [checked, setChecked] = useState<string[]>([]);
```

**Review:**

> if I delete an option's line from the message box by hand, its checkbox stays checked. adding the option back would
> then take two clicks: uncheck and then check.
>
> a minor nit, but the PR description could mention that currently the checkboxes only add text and don't track what's
> in the box.

## Example 3

**Issue:** Show a 403 page via forbidden() rather than string access states, and gate the navbar Analytics entry on
the same check.

`frontend/app/dashboard/analytics/layout.tsx`

```diff
+export default function AnalyticsLayout({ children }: { children: React.ReactNode }) {
+  const { token } = useAuth();
+  const t = useTranslations("analytics");
+  const [access, setAccess] = useState<Access>("checking");
+
+  useEffect(() => {
+    if (!token) return;
+    let active = true;
+    setAccess("checking");
+    checkPermission(token, "analytics.read")
+      .then((allowed) => {
+        if (active) setAccess(allowed ? "allowed" : "denied");
```

**Review:**

> Instead of matching string like `allowed` or `denied`. Lets simply show a 403 page if the `checkPermission` function
> returns 403. We dont even need to redirect.
>
> Something like:
> ```tsx
> import { forbidden } from 'next/navigation'
>
> checkPermission(token, "analytics.read")
>       .then((allowed) => {
>           ...
>       })
>       .catch(
>       // This is what I think we should do
>       forbidden() // Automatically renders your forbidden.tsx page with a 403 status code
>       )};
> ```
> LMK WDYT
>
> Lets also gate the navbar Analytics entry on the same check, so this page would only be accessible if someone tries
> to directly go to this URL

## Example 4

**Issue:** 'Turn' is internal terminology; rename the figure label to something like 'Messages Failed'.

`sparkth/plugins/chat/analytics/reads.py`

```diff
+        "chat.messages",
+        gettext_noop("Messages sent"),
+        _count_of(ChatMessageSent.event_type),
+        view="authoring",
+        order=50,
+    ),
+    SummaryFigure(
+        "chat.tool_calls", gettext_noop("Tool calls"), _count_of(ChatToolInvoked.event_type), view="authoring", order=60
+    ),
+    SummaryFigure(
+        "chat.failed_turns",
+        gettext_noop("Failed turns"),
```

**Review:**

> Turn is something that is an internal terminology for Sparkth, lets rename this to something like
> `"Messages Failed"`?

## Example 5

**Issue:** Rename sidebar entry from My Plugins to Settings to match code terminology.

**Review:**

> Lets also rename the Sidebar entry to `Settings` instead of `My Plugins`, because that is the terminology being used
> in the code as well
