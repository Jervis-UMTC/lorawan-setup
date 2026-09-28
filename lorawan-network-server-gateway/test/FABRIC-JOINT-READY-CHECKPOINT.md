# Joint Fabric readiness checkpoint

Our side is prepared when:
- central research contract self-test passes;
- Fabric-sync unit tests pass including intentional bad-hash rejection;
- P2 formal manifest generation is locked to the preregistered shape;
- R2/F1/F2/T1/T2 harness invariants pass the oversight audit;
- PRE/P1 remain qualified and unchanged except for stricter formal denominator validation.

When the Fabric team reports READY, do not begin counted trials immediately. Run short synchronized rehearsals in this order:
P1 -> P2 -> R2 -> A2 -> I3 -> T1/T2, then I1/I2 as their fixtures become available.

A joint trial is invalid if manifest hashes differ or any required record fails exact identity/hash correlation.
