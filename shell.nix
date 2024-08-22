{ pkgs ? import <nixpkgs> {}}:

pkgs.mkShell {
  buildInputs = with pkgs; [
    bird
    openvpn
    socat
    psmisc
    ipcalc
  ];
}
