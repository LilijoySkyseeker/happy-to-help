{
  description = "Happy to Help! music video: render it yourself";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (s: f nixpkgs.legacyPackages.${s});

      # Everything the renderer needs, with the browser and fonts pinned by nixpkgs.
      env = pkgs: rec {
        python = pkgs.python3.withPackages (p: [ p.numpy ]);
        fonts = pkgs.makeFontsConf {
          fontDirectories = [ pkgs.dejavu_fonts pkgs.liberation_ttf pkgs.noto-fonts-color-emoji ];
        };
        deps = [ pkgs.nodejs pkgs.ffmpeg python pkgs.coreutils pkgs.bash ];
        exports = ''
          export PLAYWRIGHT_BROWSERS_PATH=${pkgs.playwright-driver.browsers}
          export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true
          export NODE_PATH=${pkgs.playwright-test}/lib/node_modules
          export FONTCONFIG_FILE=${fonts}
          export FFMPEG=${pkgs.ffmpeg}/bin/ffmpeg
        '';
      };
    in
    {
      packages = forAll (pkgs:
        let e = env pkgs; in {
          # nix run github:LilijoySkyseeker/happy-to-help
          #   renders the whole video to ./happy-to-help/renders/full.mp4.
          # Inside a checkout it renders there instead. Extra arguments are the chunks
          # ("start end" pairs, one per core), e.g. nix run . -- "0 30" "30 60"
          default = pkgs.writeShellApplication {
            name = "render-happy-to-help";
            runtimeInputs = e.deps;
            text = e.exports + ''
              if [ -f render/index.html ] && [ -f flake.nix ]; then dir=$PWD
              else
                dir=$PWD/happy-to-help
                if [ ! -d "$dir" ]; then cp -r ${self} "$dir"; chmod -R u+w "$dir"; fi
              fi
              if [ $# -eq 0 ]; then set -- "0 64" "64 129" "129 193" "193 257.56"; fi
              bash "$dir/render/render-chunks.sh" full "$@"
              echo "video: $dir/renders/full.mp4"
            '';
          };
        });

      # nix develop: node, ffmpeg, python and the pinned browser, for editing and live preview.
      devShells = forAll (pkgs:
        let e = env pkgs; in {
          default = pkgs.mkShell { packages = e.deps; shellHook = e.exports; };
        });
    };
}
