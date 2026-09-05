# SocialScheduler ↔ SocialMarket Top-100 Reconciliation Contract

SocialScheduler is the execution plane. SocialMarket is the selection/intelligence plane.

## Canonical rule
A product must leave the active SocialMarket Top-100 only after provider-confirmed publication has been reconciled successfully.

## State transitions
`selected_top100` → `approved_for_social` → `claimed_by_scheduler` → `published`

A record is `published` only when SocialScheduler has provider truth sufficient to identify the execution. Workflow success alone is not enough.

## Required publication payload
When publication is confirmed, SocialScheduler must send/record:

```json
{
  "source_hash": "immutable product/content hash",
  "product_id": "stable product identity",
  "lifecycle_state": "published",
  "published_at": "ISO-8601 timestamp",
  "published_platforms": ["instagram", "facebook", "tiktok"],
  "scheduler_execution_ids": ["..."],
  "provider_post_ids": ["..."],
  "provider": "buffer"
}
```

## Idempotency
- Repeated ACK for the same `(source_hash, platform, provider_post_id)` must be safe.
- Existing published state must not create a second post.
- If provider create succeeds but SocialMarket ACK fails, reconciliation must retry ACK only; it must not recreate the provider post.

## Active-list exclusion
SocialMarket Top-100 optimization excludes any record with provider-confirmed `published` state or populated `published_at + provider_post_ids`.
