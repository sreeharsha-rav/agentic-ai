# System Architecture

The system uses a Redis cache layer in front of the primary PostgreSQL
database to reduce latency for repeated read queries. The API gateway
routes all incoming requests through an authentication layer before
reaching the cache.

## Caching Strategy

Cache entries expire after five minutes. Write operations invalidate the
corresponding cache key immediately to avoid serving stale data to clients.

# Deployment Process

Deployments are triggered automatically whenever a change is merged to the
main branch. The CI pipeline runs the full test suite before promoting a
build to the staging environment.
