{
  description = "piebird plugins and development tooling";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs =
    { self, nixpkgs, ... }:
    let
      systems = [
        "aarch64-darwin"
        "x86_64-darwin"
        "aarch64-linux"
        "x86_64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
        in
        {
          default = pkgs.bun;
          # What the demo machine (tools/demo/vm/machine.pkr.hcl) runs the recorder with, besides
          # omp and Tern: Bun for the recorder and omp's plugin installs, ffmpeg for the videos,
          # Git for the demo projects (macOS has only a stub until the developer tools are installed).
          demo-machine = pkgs.buildEnv {
            name = "piebird-demo-machine";
            paths = [
              pkgs.bun
              pkgs.ffmpeg-headless
              pkgs.git
            ];
          };
        }
      );

      devShells = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
        in
        {
          default = pkgs.mkShell {
            packages = [
              pkgs.bun
              pkgs.gh
              pkgs.git
              pkgs.jq
              pkgs.nixfmt
              # Luau lint and format (selene.toml, stylua.toml).
              pkgs.selene
              pkgs.stylua
              # The plugins' native programs (go.mod): Go builds and tests them, fetching the exact
              # toolchain go.mod names; golangci-lint lints and formats them (.golangci.yml).
              # govulncheck is a tool in go.mod, built by that same toolchain.
              pkgs.go_1_27
              pkgs.golangci-lint
              # Demo videos (bun tools/demo/record.ts): ffmpeg encodes the MP4 and the WebP;
              # tesseract reads a video made on this Mac for the login name (tools/demo/onscreen.ts).
              pkgs.ffmpeg-headless
              pkgs.tesseract
              # Python for analysis (tools/bench/): uv installs and locks its packages
              # (pyproject.toml, uv.lock) on this Python, never one it downloads.
              pkgs.python3
              pkgs.uv
            ]
            # Demos recorded in a macOS virtual machine (docs/demos.md): Packer builds its image
            # with its tart plugin, tart runs it.
            ++ pkgs.lib.optionals pkgs.stdenv.hostPlatform.isDarwin [
              pkgs.packer
              pkgs.tart
            ];
            UV_PYTHON = "${pkgs.python3}/bin/python3";
            UV_PYTHON_DOWNLOADS = "never";
          };
        }
      );

      formatter = forAllSystems (system: (pkgsFor system).nixfmt);

      checks = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
        in
        {
          bun-version = pkgs.runCommand "omp-bun-version" { nativeBuildInputs = [ pkgs.bun ]; } ''
            bun --version > "$out"
          '';

          marketplace =
            pkgs.runCommand "omp-marketplace-catalog"
              {
                nativeBuildInputs = [ pkgs.jq ];
                src = self;
              }
              ''
                jq -e '.name and (.plugins | type == "array")' "$src/.omp-plugin/marketplace.json" > /dev/null
                touch "$out"
              '';
        }
      );
    };
}
