---
title: Database schema
---

[Documentation index]({{ site.baseurl }}{% link index.md %})

`schema/bmdynip-schema-v1.sql` defines the MariaDB schema used by the updater and
Web UI APIs. The [installer]({{ site.baseurl }}{% link pages/installation.md %})
applies it during installation and upgrades, retaining existing records.

The model follows [OMG CWM 1.1](https://www.omg.org/spec/CWM/1.1/PDF/),
sections 5.7 and 16.3–16.4, with CMDB's storage customizations. Model elements
allocate their ID in `ModelElement`; inheritance tables reuse that ID. Names
and namespace ownership stay on the parent. `Component` inherits `Namespace`,
`SoftwareSystem` uses `Package` as its stored parent, and `Machine` retains
CMDB's `macAddress`, `site`, `createdOn`, and `updatedOn` fields.

TekSavvy is a `DataManager`. The router is a `Machine` whose deployed client
software is a `DataProvider`. Its `ProviderConnection` references TekSavvy and
is owned by the provider through `ModelElement.namespace`. The explicit owner
and namespace must agree. Deployment ownership follows the same CMDB constraint.
The upstream DataManager also requires its deployment, component, and machine
ancestors; the schema does not seed or invent their values.

Use `TaggedValue` with `tag="publicIpAddress"` on the connection for its current
public IP. Each DNS-record change has one `ChangeRequest`, with a historical
fully qualified `hostname` tagged value. The unique `(modelElement, tag)` key
allows one value per attached tag. DNS records are application data in
`DnsRecord`; they do not inherit `ModelElement`. Deleting a DNS record does not
delete its change history. `DnsRecord.address` is nullable until an address has
been successfully applied to that record.

`ModelElementChangeRequest` associates requests with affected model elements.
Its `position` column stores each element's ordered request collection. Multiple
affected elements remain possible; one request still describes only one DNS
record. Self-association and a completion date on an incomplete request are
rejected by database constraints. Status remains a string as defined by CWM.

The future domain database interface must create the request, at least one
affected-element association, and its hostname tag in one transaction. Ordinary
foreign keys cannot enforce the minimum association count or required tag on
the parent row. External DNS names and public IPv4 addresses must be validated
at the application boundary. Store change-request dates in UTC.

For database integration checks against an explicitly supplied disposable
MariaDB instance:

```sh
BMDYNIP_TEST_DB_SOCKET=/path/to/test.sock python3 -m unittest discover -s tests -p test_schema.py -v
```
