"""Coverage instruments: who is in scope, who we found, who outside sources say we missed.

  python -m coverage.ledger      people ledger: every roster row -> one person -> one outcome
  python -m coverage.probes      independent sources (CSRankings, NSF CAREER) -> data/probes/*.jsonl
  python -m coverage.check       the done predicate, per school; exit 1 while anything is open
"""
