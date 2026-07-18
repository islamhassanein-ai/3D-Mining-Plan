# Phase 0 Research: Phase 1 Collaboration & Multi-Tenancy

No `NEEDS CLARIFICATION` markers remain in the Technical Context — the one open
question in the spec itself (share-link login model) was resolved via clarification
before planning began. The decisions below are the implementation-level choices
needed to build it.

## Decision 1: Share-link token generation

**Decision**: Generate tokens with `secrets.token_urlsafe(32)` (Python standard
library), stored as the `share_link.token` column, indexed and unique.

**Rationale**: `secrets` is specifically designed for security-sensitive random
values (unlike `random`), needs no new dependency (Principle III), and
`token_urlsafe(32)` yields 256 bits of entropy — effectively unguessable by brute
force, satisfying spec FR-005's "long and unguessable" requirement.

**Alternatives considered**: UUID4 as the token — rejected; UUIDs are designed for
uniqueness, not secrecy, and have less effective entropy against a determined
guesser than a purpose-built token.

## Decision 2: Default expiry window and renewal

**Decision**: Share links default to a 7-day expiry from creation. The owner can
renew an active (not yet expired or revoked) link, which extends `expires_at` by
another 7 days from the renewal time — the token itself does not change on renewal.

**Rationale**: The spec (FR-005) requires *a* bounded expiry but doesn't pin an
exact duration — 7 days is long enough to cover a typical review window for a
colleague without requiring the owner to constantly reissue links, short enough to
bound the "leaked link" exposure window meaningfully. Renewing in place (same token)
rather than issuing a new URL avoids breaking a link the colleague may have already
opened/bookmarked.

**Alternatives considered**: No renewal (owner must create a new link after expiry)
— rejected, adds friction against the "lightweight sharing" goal for a legitimately
still-needed link; a much longer default (30+ days) — rejected, weakens the exposure
bound without a stated need.

## Decision 3: Enforcing read-only at the API layer

**Decision**: Requests authenticated via a share-link token resolve to a
request-scoped "viewer context" (project_id + read-only flag) distinct from the
normal JWT-based user context from feature 003. Every mutating route (imports,
project creation, share-link management, etc.) requires the JWT user context and
explicitly rejects the viewer context; only a small set of read routes (scene,
collar detail, true-thickness) accept either context, scoped to the token's
`project_id`.

**Rationale**: This makes "read-only" a structural property enforced once, in the
dependency each route declares, rather than a check individual endpoints could
forget to add — directly satisfies FR-004 and SC-002 without duplicating logic
across every route.

**Alternatives considered**: A single unified user/session concept with a
`can_write` boolean — rejected; conflating the two contexts risks a future mutating
route accidentally accepting a viewer token if a check is missed. Two distinct,
narrowly-scoped dependencies make the omission harder, not just possible-but-checked.

## Decision 4: Project switch performance

**Decision**: The workspace project list (`GET /workspace/projects`) returns
lightweight metadata only (id, name, commodity — not scene data). Switching
projects re-invokes feature 003's existing `GET /projects/{id}/scene` endpoint and
scene-loader code with the new `project_id`, reusing the same JWT session — no
re-authentication, no new scene-loading code path.

**Rationale**: Reusing feature 003's scene loader directly is both the "boring"
choice (Principle III) and the fastest path to the 5-second switch target (SC-001),
since it's already built and doesn't need a second implementation to stay in sync
with.

**Alternatives considered**: Pre-loading all projects' scene data on workspace open
— rejected, wasteful and unnecessary for a 1-3 project scale, and works against the
empty-state/loading-state discipline established in feature 003.
