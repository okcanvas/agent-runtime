# OKCanvas Node CLI development harness

This workspace is a development and acceptance-test harness for the Runtime Control API. It is not yet the future multi-user Product CLI or a promoted service client.

It currently uses local administrator and Run-submitter credentials and may call development API surfaces. Do not distribute it as a service client. Any future promotion must use only `/v1/service/**`, external Bearer authentication, tenant/principal-scoped resources, persisted SSE, and service Artifact APIs without importing Runtime implementation modules.
