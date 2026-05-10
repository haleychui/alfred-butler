# Alice -> Alfred Integration Notes

Alice is an employee secretary platform. Alfred is a mobile-first butler for a person, a home, and an office.

Integrated into Alfred:
- Alice-style file map summary backfill: `vault_file_summaries`
- Mac extracted-content backfill into Vault summaries and keyword weights
- Alice-style observable query plan for office file search
- Alice-style materialization ledger: `vault_file_materializations`
- Admin endpoints:
  - `POST /api/admin/vault/backfill-summaries`
  - `GET /api/admin/vault/summaries`
  - `POST /api/admin/vault/backfill-mac-content`
  - `GET /api/admin/vault/search-plan`
- Vault search now uses summary text when available, with query expansion, summary-hit boosts, and recency boosts.

Useful Alice capabilities already matched or partially matched in Alfred:
- LINE async reply/push pattern
- Drive fuzzy search and OCR summary concepts
- Group chat/group file context
- File map audit/feedback

Still candidates for later:
- LINE Aho-Corasick fast intent router
- Gmail unread summary and draft-confirm-send workflow
- Meeting diarization/speaker recognition via pyannote
- Provider chain / local vLLM task routing
- Computer-use screenshot/form-fill with explicit confirmation
