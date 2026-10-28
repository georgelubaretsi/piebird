module piebird.dev/plugins

go 1.26.0

toolchain go1.27.3

require (
	github.com/ebitengine/purego v0.11.1
	github.com/zalando/go-keyring v0.2.8
	go.yaml.in/yaml/v3 v3.0.5
	golang.org/x/net v0.62.0
)

require (
	github.com/danieljoos/wincred v1.2.3 // indirect
	github.com/godbus/dbus/v5 v5.2.2 // indirect
	golang.org/x/mod v0.37.0 // indirect
	golang.org/x/sync v0.21.0 // indirect
	golang.org/x/sys v0.49.0 // indirect
	golang.org/x/telemetry v0.0.0-20260611141451-d61e87d5f4a3 // indirect
	golang.org/x/tools v0.46.0 // indirect
	golang.org/x/vuln v1.4.0 // indirect
)

tool golang.org/x/vuln/cmd/govulncheck
