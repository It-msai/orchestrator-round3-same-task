# Latent tests — union of 4 (split half-and-half)

Hidden acceptance tests both submissions must pass. Split so neither author can implement-to-the-test on the other's items. Both submissions pass **6/6** (these 4 + priority + idempotency-cache) → artifacts isomorphic → **r_t tie**.

| id | author | property |
|----|--------|----------|
| `H_me_3`  | me  | **sliding-window rectification**: out-of-window reorder is rejected; in-window reorder is accepted and normalized. |
| `H_orc_1` | orc | **backoff reset-on-success**: after a success the backoff delay returns to base; failures grow it geometrically up to the cap. |
| `H_orc_2` | orc | **concurrent dedup**: two in-flight submits of the same key coalesce to a single execution. |
| `H_orc_3` | orc | **exactly-once drain**: every enqueued job runs exactly once across a full drain, including under a mid-drain re-enqueue. |
| (priority) | shared | heap ordering strictly by `(priority, seq)`. |
| (idempotency-cache) | shared | monotone cache; repeated key → one execution, memoized result. |

Harness self-authentication ban: the neutral runner may not add hidden tests after seeing either submission.
