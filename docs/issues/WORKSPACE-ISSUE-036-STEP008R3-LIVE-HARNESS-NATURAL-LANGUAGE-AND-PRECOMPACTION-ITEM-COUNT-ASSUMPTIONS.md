# WORKSPACE-ISSUE-036

## Failure

The STEP008R3 Windows Live run functionally succeeded for all four short utterances but the formal harness returned 27/29.

## Proven causes

- The empty-result predicate searched the Korean answer text for three substrings and rejected the valid wording `검색되지 않았습니다`.
- The Session predicate required the current `item_count` to remain even and at least eight after four turns. The runtime legitimately compacted 16 input items to five after the fourth committed turn.

## Correction

- Validate empty search results from structured Tool normalization evidence rather than answer wording.
- Validate continuity from `session.turn.completed` events and monotonic turn counts rather than the post-compaction current item count.

## Recurrence prevention

Live acceptance must not bind semantic correctness to language-specific prose when structured result fields exist. A mutable/compacted store's current size must not be used as proof that historical commits occurred.
