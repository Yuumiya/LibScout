{
  system ? builtins.currentSystem,
  sources ? import ./npins,
  pkgs ? import sources.nixpkgs { inherit system; },
}:
{
  shell = pkgs.mkShell {
    packages = [
      pkgs.python3
      pkgs.uv
    ];
  };
}
