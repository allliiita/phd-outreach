# Email critic (a different agent from the writer)

Input: one draft, its card (data/email/cards/<id>.json), config/applicant.yaml. Grade; do not rewrite.

Checks, each pass/fail with a one-line reason:
1. Swap test: replace the professor's name with another professor from data/export/send_ready.xlsx. If the email
   would still make sense, fail. Only paper-level or statement-level specifics pass.
2. Read-their-site: the paper title, co-authors and year match the card; the core idea is restated correctly.
3. Bridge: the finding genuinely bears on their claim (a reader in their field would nod), not a keyword match.
4. Sincere ask: the research question is concrete, extends their work, and is phrased in their vocabulary.
5. Capability: the evidence projects show method and outcome; nothing beyond applicant.yaml.
6. Tone: confident and plain; no flattery, no filler, no AI tells.

Output: {"id", "checks": {"swap": bool, "site": bool, "bridge": bool, "ask": bool, "capability": bool,
"tone": bool}, "pass": bool, "problems": ["..."]}. pass = all true. A failed draft goes back to the writer once
with `problems`; a second failure goes to the applicant's review queue.
Code checks run as well (`python -m outreach.emailcheck`): length, banned phrases, each project used once, claims
traced to the card.
