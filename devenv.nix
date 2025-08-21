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
  packages = [
    pkgs.git
    pkgs.black
    pkgs.ty
    pkgs.isort
  ];

  # https://devenv.sh/languages/
  languages = {
    python = {
      enable = true;
      directory = "./backend";
      uv = {
        enable = true;
        sync.enable = true;
      };
      # NOTE(shackra): required for ty
      venv = {
        enable = true;
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
  scripts.format.exec = ''
    echo "isort"
    ${pkgs.isort}/bin/isort --sg 'src/divinum-officium/**/*.py' --om ${config.devenv.root}/backend
    echo "black"
    ${pkgs.black}/bin/black --exclude 'src/divinum-officium/.*/.*\.py' ${config.devenv.root}/backend
  '';

  scripts.unittest.exec = ''
    cd ${config.devenv.root}/backend
    pytest --failed-first .
  '';

  scripts.check.exec = ''
    cd ${config.devenv.root}/backend
    ${pkgs.ty}/bin/ty check
  '';

  enterShell = ''
    hello
    git --version
    echo "yarn version `yarn --version`"
    uv --version
  '';

  # https://devenv.sh/tasks/
  # tasks = {
  #   "myproj:setup".exec = "mytool build";
  #   "devenv:enterShell".after = [ "myproj:setup" ];
  # };

  # https://devenv.sh/tests/
  enterTest = '''';

  # https://devenv.sh/git-hooks/
  git-hooks.hooks = {
    shellcheck.enable = true;
    black.enable = true;
    #uv.enable = true; # NOTE(shackra): not available yet?
    isort.enable = true;
    biome.enable = true;
    nil.enable = true;
    commitizen.enable = true;
  };

  # See full reference at https://devenv.sh/reference/options/
}
