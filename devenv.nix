{
  pkgs,
  config,
  ...
}:

{
  # https://devenv.sh/basics/
  env.GREET = "devenv";
  env.TEST_ONLY_DO_FILES_PATH = "${config.devenv.root}/backend/src/divinum-officium/web/www/missa";

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
  enterTest = ''
    cd ${config.devenv.root}/backend
    mypy .
    pytest --failed-first .
  '';

  # https://devenv.sh/git-hooks/
  git-hooks.hooks = {
    shellcheck.enable = true;
    black.enable = true;
    uv-check.enable = true;
    uv-lock.enable = true;
    isort.enable = true;
    mypy = {
      enable = true;
      settings = {
        binPath = "${config.devenv.root}/.devenv/state/venv/bin/mypy";
      };
    };
    biome.enable = true;
    nil.enable = true;
    commitizen.enable = true;
  };

  # See full reference at https://devenv.sh/reference/options/
}
