{ pkgs ? import <nixpkgs> {}}:

pkgs.mkShell {
  buildInputs = with pkgs; [
    bird2
    openvpn
    socat
    psmisc
    ipcalc
  ];
}
