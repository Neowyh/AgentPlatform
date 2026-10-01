# Product release records

> status: current
> owner: product-line maintainers

Before creating an `ideer-VERSION` release, commit `docs/releases/ideer-VERSION.md` on the containing `product/offline-*` maintenance branch. The record starts with `upstream_baseline: SHA`, `product_branch: product/offline-X.x`, and `verification_command: current candidate command`, and `verification_result: passed`. Include absorbed and rejected upstream changes and the offline compatibility conclusion. Historical results do not validate a new candidate.

The reusable release workflow checks the tag prefix, tagged candidate, containing origin product branch, committed record, and backend/frontend/chart version agreement through `bash scripts/check_product_release.sh ideer-VERSION`. Main mirror updates never publish a product release.
