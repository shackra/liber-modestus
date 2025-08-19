{
  pkgs,
  lib,
  config,
  inputs,
  ...
}:

{
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  # https://devenv.sh/packages/
  packages = [ pkgs.git ];

  # https://devenv.sh/languages/
  languages = {
    python = {
      enable = true;
      directory = "./backend";
      uv = {
        enable = true;
        # sync.enable = true;
      };
    };

    javascript = {
      enable = true;
      directory = "./frontend";
      yarn = {
        enable = true;
        # install.enable = true;
      };
    };
  };

  # https://devenv.sh/processes/
  # processes.cargo-watch.exec = "cargo-watch";

  # https://devenv.sh/services/
  # services.postgres.enable = true;

  # https://devenv.sh/scripts/
  scripts.hello.exec = ''
    echo hello from $GREET
  '';

  enterShell = ''
    hello
    git --version
    echo "yarn version `yarn --version`"
    echo "uv version `uv --version`"
  '';

  # https://devenv.sh/tasks/
  # tasks = {
  #   "myproj:setup".exec = "mytool build";
  #   "devenv:enterShell".after = [ "myproj:setup" ];
  # };

  # https://devenv.sh/tests/
  enterTest = ''
    echo "Running tests"
    git --version | grep --color=auto "${pkgs.git.version}"
  '';

  # https://devenv.sh/git-hooks/
  git-hooks.hooks = {
    shellcheck.enable = true;
    black.enable = true;
    biome.enable = true;
    nil.enable = true;
    commitizen.enable = true;
  };

  # See full reference at https://devenv.sh/reference/options/
}
