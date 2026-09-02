# Infrastructure

Infrastructure is grouped by deployable service.

- `scholar/` contains the current Scholar data-plane dependencies.
- `proxy-hub/` is reserved for the Phase Two control-plane dependencies.

The directories must remain independently deployable. Proxy Hub must access Scholar through its authenticated service interface rather than through Scholar database credentials.
