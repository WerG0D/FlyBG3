# Combat reward design

`RewardEngine` receives only `CombatOutcome` after `arena.step` or a future adapter returns. No action label receives a bonus. A policy may propose `BASIC_ATTACK` out of range and receives only the invalid-action penalty and the turn consequences.

| Observed outcome | Default value |
| --- | ---: |
| Damage dealt | +0.02 per HP |
| Damage received | −0.02 per HP |
| Enemy killed | +1 |
| Flyman killed | −1 |
| Victory | +3 |
| Defeat | −3 |
| Invalid action | −0.05 |
| Turn-limit timeout | −1 |

`RewardBreakdown` stores all eight terms and their total. Timeout is not a victory. The terminal penalty prevents indefinitely retreating to obtain zero reward; it rewards an outcome, not a particular action. The synthetic arena uses non-regenerating HP.

In real BG3, causal attribution requires target UUIDs, source-of-damage events, other party members, summons, regeneration, and target identity. Without that instrumentation, HP differences must not be assigned to Flyman. Future guards include a turn limit, terminal rewards, a 1v1 target, damage-source logs, and evaluation against different enemies. Coefficients are engineering hypotheses, not a biological motivation scale.
