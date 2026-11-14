<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.

## What Lovable manages

Rules outside this block are the project's own. Change the pieces below in
Lovable, not by hand. With the [Lovable MCP](https://mcp.lovable.dev)
connected, `send_message` asks Lovable to do it; otherwise ask the user to
use the editor.

- **Database.** Do not add or edit `supabase/migrations/` or `drizzle/`.
  Ask Lovable to change the schema.
- **Generated files.** Do not edit a file whose header says it is automatically
  generated.
- **AI gateway.** Keep model calls on Lovable's gateway, and keep
  `LOVABLE_API_KEY` out of browser code.
- **Connectors.** Lovable provides native connectors. `list_connectors` shows
  which are enabled; `add_connector` only returns the dashboard link. When a
  connector is enabled, calls go through the connector gateway and need
  `LOVABLE_API_KEY`. When Lovable does not provide one, users can bring their
  own key and store it in Secrets.
- **Secrets.** Lovable manages them. Do not put secret values in the repo.
<!-- LOVABLE:END -->

## ARA architecture
- Use TanStack routes and a root React context for session-only inputs, results, and chat; navigation must not discard the current calculation.
- Define ARA's context identity in a separate non-component module and preserve only that identity during hot updates; replacing context objects can disconnect mounted consumers from their provider.
- Centralize the external API URL and request/body adapters in the ARA API module; frontend code must not calculate tax outcomes.
- Keep payment activation unavailable until a real checkout session can be verified; a success URL alone never grants Pro.
- Centralize visible UI copy in the EN/RU/ES dictionary and backend language mapping; Spanish requests use English.
- Keep form guidance a presentation mapping of backend residency status, with no date-based or visa-based residency inference; visas may only annotate Form 8843 for an already-returned nonresident status.
