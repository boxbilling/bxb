# Testing in bxb

## Overview

The reliability and correctness of bxb is achieved in part by thorough and careful
testing. This document describes the testing strategy and explains what is included
in this open-source repository versus what lives in the private `bxb-internal`
repository.

## What You See Here: Smoke Tests

The tests in this directory are **smoke tests** — a small set of high-level checks
that verify the application boots, core CRUD operations work, and API endpoints
respond correctly. Think of them as a quick sanity check: if these pass, the
fundamental wiring of the system is intact.

Run them with:

```bash
make test
```

These smoke tests are designed to run fast (seconds, not minutes) and are executed
before every commit.

## The Full Test Suite Lives Elsewhere

The complete test suite — with **100% code coverage enforcement** — is maintained in
the private `bxb-internal` repository. It is not part of this open-source release.

This is a deliberate architectural decision, not an oversight.

### The test code is much larger than the product itself

Roughly 50 lines of test code exist for every line of product code, bxb's full test suite dwarfs the
application it verifies. The internal test infrastructure includes:

- **Exhaustive unit tests** for every model, service, and utility function
- **Integration tests** covering complex multi-step billing workflows (metering
  through invoicing through payment collection)
- **Edge-case and boundary testing** for currency arithmetic, proration logic,
  timezone handling, rounding behavior, and plan migration scenarios
- **Concurrency and race-condition tests** for event ingestion and usage aggregation
- **API contract tests** ensuring backward compatibility across versions
- **Regression tests** for every bug ever fixed — once a bug is caught, it stays
  caught

The sheer volume of this test code — the fixtures, the helpers, the scenario
generators, the assertion libraries — constitutes a larger engineering effort than
the billing engine itself. Releasing it would effectively mean maintaining two
large open-source projects instead of one.

### Why not open-source the tests?

A few practical reasons:

1. **Maintenance burden.** Keeping a test suite of this scale healthy requires
   continuous investment. Decoupling it from the internal CI/CD pipeline and
   release process would create significant overhead with little community benefit.

2. **Internal infrastructure dependencies.** The full suite relies on internal
   tooling, test databases, seed data generators, and CI infrastructure that are
   not portable without substantial adaptation work.

3. **The smoke tests are sufficient for contributors.** If you are contributing to
   bxb, the smoke tests in this directory will catch breakage in the core paths.
   Submitted pull requests are run against the full internal suite before merging.

## For Contributors

If you are contributing to bxb:

- Run `make test` before submitting a pull request
- The smoke tests must pass — they are the minimum bar
- Your PR will be validated against the full internal test suite by a maintainer
  before it is merged
